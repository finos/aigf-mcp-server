"""``calm/architecture.json`` describes the server the code builds.

The file is the FINOS CALM 1.2 description of this server: its nodes,
interfaces, relationships, flows and controls (#270, from the assessment in
#269). ``calm validate --strict`` checks it against the CALM schemas and
checks each control's configuration against the requirement schema under
``calm/controls/`` it names; that needs Node and runs by hand
(``docs/development.md``). The files live outside ``docs/`` because every file
there must be Markdown the documentation scanners read. The CLI cannot know what the code does, so these
tests compare the file with the code: the transports the settings accept, the
routes a server with authentication mounts and which of them answer without a
token, the listen address, the hosts the content client may reach and whether
it follows a redirect, the claims the verifier refuses a token for, the
settings the file names and the static catalog it falls back to.
They also repeat the CLI's reference checks, so a broken reference is found
in CI and not only by hand.

The descriptions are prose. Where one states a number or a name the code
holds (the probe interval and file, the JWKS fetch interval, the list file's
size limit and directory mode), the number is read out of the sentence and
compared (#324); the rest of the prose is compared with nothing. The CALM
schema check itself does not run here.
"""

from __future__ import annotations

import inspect
import json
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, get_args
from urllib.parse import urlparse

import httpx
import pytest
from fastmcp import FastMCP
from joserfc import jwt
from joserfc.jwk import RSAKey
from jsonschema import Draft202012Validator

from finos_mcp import fastmcp_server, http_health
from finos_mcp.app import _build_auth_provider
from finos_mcp.config import ENV_FILE_VARIABLE, Settings
from finos_mcp.content import list_file, static_catalog
from finos_mcp.content.fetch import _DEFAULT_FETCH_HOSTS, HTTPClient
from finos_mcp.security import content_filter, jwt_verifier

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_ARCHITECTURE = _ROOT / "calm" / "architecture.json"
_CONTROLS = _ROOT / "calm" / "controls"
_DEPLOYMENT_GUIDE = _ROOT / "docs" / "deployment.md"

_CALM_1_2 = "https://calm.finos.org/release/1.2/meta/calm.json"
_SERVER = "finos-mcp-server"
_METADATA_INTERFACE = "oauth-protected-resource-metadata"
_HEALTH_CONTROL = "open-health-urls"
_SETTING = re.compile(r"\bFINOS_MCP_[A-Z0-9_]+\b")

_ISSUER = "https://auth.example.com"
_AUDIENCE = "finos-mcp-server"
_Transport = Literal["http", "streamable-http", "sse"]


def _authenticated_settings(public_pem: str, **overrides: object) -> Settings:
    """Settings for a networked server that checks tokens against ``public_pem``."""
    values: dict[str, object] = {
        "mcp_transport": "http",
        "mcp_auth_enabled": True,
        "mcp_auth_public_key": public_pem,
        "mcp_auth_issuer": _ISSUER,
        "mcp_auth_audience": _AUDIENCE,
    }
    values.update(overrides)
    return Settings(**values)


def _token(private_pem: bytes, **changes: Any) -> str:
    """An RS256 token the verifier accepts, with ``changes`` applied (None drops)."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": "alice",
        "iat": now,
        "exp": now + 300,
    }
    for name, value in changes.items():
        if value is None:
            del claims[name]
        else:
            claims[name] = value
    return jwt.encode(
        {"alg": "RS256", "typ": "JWT"}, claims, RSAKey.import_key(private_pem)
    )


def _architecture() -> dict[str, Any]:
    loaded = json.loads(_ARCHITECTURE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{_ARCHITECTURE} is not a JSON object"
    return loaded


def _node(architecture: dict[str, Any], unique_id: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [
        node for node in architecture["nodes"] if node["unique-id"] == unique_id
    ]
    assert len(found) == 1, f"expected one node {unique_id!r}, found {len(found)}"
    return found[0]


def _relationship(architecture: dict[str, Any], unique_id: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [
        relationship
        for relationship in architecture["relationships"]
        if relationship["unique-id"] == unique_id
    ]
    assert len(found) == 1, (
        f"expected one relationship {unique_id!r}, found {len(found)}"
    )
    return found[0]


def _interfaces(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    interfaces = {
        interface["unique-id"]: interface for interface in node.get("interfaces", [])
    }
    assert len(interfaces) == len(node.get("interfaces", [])), (
        f"node {node['unique-id']!r} repeats an interface id"
    )
    return interfaces


def _paths(interface: dict[str, Any]) -> list[str]:
    return [interface["path"]] if "path" in interface else interface.get("paths", [])


def _controls(
    architecture: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """``(where, control id, control)`` for every control the file holds."""
    holders: list[tuple[str, dict[str, Any]]] = [("architecture", architecture)]
    for key in ("nodes", "relationships", "flows"):
        holders += [(f"{key} {item['unique-id']}", item) for item in architecture[key]]
    for where, holder in holders:
        for control_id, control in holder.get("controls", {}).items():
            yield where, control_id, control


def _control_config(architecture: dict[str, Any], control_id: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [
        requirement["config"]
        for _, found_id, control in _controls(architecture)
        if found_id == control_id
        for requirement in control["requirements"]
    ]
    assert len(found) == 1, f"expected one {control_id!r} control, found {len(found)}"
    return found[0]


def _routes(transport: _Transport) -> set[str]:
    app: Any = fastmcp_server.mcp.http_app(transport=transport)
    return {str(route.path) for route in app.routes}


def _served_with_auth(public_pem: str, transport: _Transport) -> Any:
    """The HTTP app of a server with authentication on and its public URL set.

    The assembled server is built from the test environment, where no auth is
    configured, and fastmcp mounts the sign-in document only when it is, so
    the routes are read off a server built the way ``app.py`` builds one with
    the health routes registered.
    """
    app_settings = _authenticated_settings(
        public_pem, mcp_transport=transport, mcp_auth_base_url="https://mcp.example.com"
    )
    server = FastMCP("calm-probe", auth=_build_auth_provider(app_settings))
    http_health.register_health_routes(server)
    return server.http_app(transport=transport)


def _route_methods(app: Any) -> dict[str, set[str]]:
    """Path to methods for every route; a mount has none."""
    return {
        str(route.path): set(getattr(route, "methods", None) or [])
        for route in app.routes
    }


def test_the_file_is_on_calm_1_2_and_every_reference_resolves() -> None:
    """The CLI's own reference checks, repeated so CI sees a broken reference."""
    architecture = _architecture()
    assert architecture["$schema"] == _CALM_1_2

    nodes = {node["unique-id"]: node for node in architecture["nodes"]}
    assert len(nodes) == len(architecture["nodes"]), "a node id is repeated"
    relationships = {
        relationship["unique-id"]: relationship
        for relationship in architecture["relationships"]
    }
    assert len(relationships) == len(architecture["relationships"]), (
        "a relationship id is repeated"
    )

    referenced: set[str] = set()
    for unique_id, relationship in relationships.items():
        ((kind, ends),) = relationship["relationship-type"].items()
        assert kind == "connects", f"{unique_id}: this file uses connects only"
        for end in ("source", "destination"):
            node = ends[end]["node"]
            assert node in nodes, f"{unique_id}: {end} node {node!r} does not exist"
            referenced.add(node)
            declared = set(_interfaces(nodes[node]))
            for interface in ends[end].get("interfaces", []):
                assert interface in declared, (
                    f"{unique_id}: node {node!r} has no interface {interface!r}"
                )
    unreferenced = sorted(set(nodes) - referenced)
    assert not unreferenced, f"no relationship references these nodes: {unreferenced}"

    flows = {flow["unique-id"]: flow for flow in architecture["flows"]}
    assert len(flows) == len(architecture["flows"]) >= 2, (
        "the normal and the fallback path each need a flow"
    )
    for unique_id, flow in flows.items():
        numbers = [transition["sequence-number"] for transition in flow["transitions"]]
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"flow {unique_id}: sequence numbers are {numbers}"
        )
        for transition in flow["transitions"]:
            assert transition["relationship-unique-id"] in relationships, (
                f"flow {unique_id}: relationship "
                f"{transition['relationship-unique-id']!r} does not exist"
            )


def test_every_control_configuration_meets_its_requirement_schema() -> None:
    """The requirement schemas are this repository's, so they are read here too.

    Each ``requirement-url`` is a path relative to the repository root, which is
    how the CLI resolves it when run from there, and the configuration is
    inline so the file is complete on its own.
    """
    architecture = _architecture()
    controls = list(_controls(architecture))
    assert len(controls) >= 3, (
        "expected the three controls left of #270's four after #302 removed "
        f"cache-integrity, found {len(controls)}"
    )

    for where, control_id, control in controls:
        assert control["description"].strip(), f"{where} {control_id}: no description"
        for requirement in control["requirements"]:
            url = requirement["requirement-url"]
            path = _ROOT / url
            assert "://" not in url and path.is_file() and path.parent == _CONTROLS, (
                f"{where} {control_id}: requirement-url {url!r} is not a file under "
                f"{_CONTROLS.relative_to(_ROOT)}"
            )
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            # The CLI's file loader refuses a schema without an $id (measured
            # with @finos/calm-cli 1.62.0), and the $id is where the file lives.
            assert schema.get("$id", "").endswith(f"/{url}"), (
                f"{url}: $id {schema.get('$id')!r} does not end with the file's path"
            )
            assert schema.get("additionalProperties") is False, (
                f"{url}: a configuration may hold keys the schema does not define"
            )
            assert {"control-id", "name", "description"} <= set(schema["required"]), (
                f"{url}: the fields the CALM control-requirement schema needs are optional"
            )
            assert "config" in requirement and "config-url" not in requirement, (
                f"{where} {control_id}: the configuration is not inline"
            )
            errors = sorted(
                Draft202012Validator(schema).iter_errors(requirement["config"]),
                key=lambda error: str(error.path),
            )
            assert not errors, f"{where} {control_id}: " + "; ".join(
                f"{list(error.path)}: {error.message}" for error in errors
            )
            assert requirement["config"]["control-id"] == control_id


def test_the_server_interfaces_name_every_transport_once() -> None:
    architecture = _architecture()
    expected = set(get_args(Settings.model_fields["mcp_transport"].annotation))
    interfaces = _interfaces(_node(architecture, _SERVER))
    named = sorted(
        transport
        for interface in interfaces.values()
        for transport in interface.get("transports", [])
    )
    assert named == sorted(expected), (
        f"the server's interfaces name the transports {named}; "
        f"FINOS_MCP_MCP_TRANSPORT accepts {sorted(expected)}"
    )

    authentication = _control_config(architecture, "authentication")
    required = set(authentication["required-on-transports"])
    exempt = set(authentication["exempt-transports"])
    assert (required | exempt, required & exempt) == (expected, set()), (
        "every transport is either required to authenticate or exempt, not both"
    )
    for unique_id, interface in interfaces.items():
        if "transports" not in interface:
            continue
        is_exempt = set(interface["transports"]) <= exempt
        assert (interface["authentication"] == "none") == is_exempt, (
            f"interface {unique_id}: authentication {interface['authentication']!r} "
            f"disagrees with the authentication control"
        )


async def test_the_server_interfaces_name_the_routes_the_server_mounts(
    key_pair: tuple[bytes, str],
) -> None:
    """Every path, its methods, and whether it answers without a token.

    The server is built with authentication on (#324): that is the only way
    the sign-in document is mounted, and the only way a route can be asked
    whether it needs a token. Each declared path is then requested without
    one, and must answer 401 exactly when its interface says a token is
    needed. A route that stops asking for a token, or a new open route, fails
    here.
    """
    _, public_pem = key_pair
    architecture = _architecture()
    interfaces = _interfaces(_node(architecture, _SERVER))
    declared: dict[str, dict[str, Any]] = {}
    for interface in interfaces.values():
        for path in _paths(interface):
            assert path not in declared, f"{path} is declared twice"
            declared[path] = interface

    served = {
        transport: _served_with_auth(public_pem, transport)
        for transport in ("http", "streamable-http", "sse")
    }
    mounted: dict[str, set[str]] = {}
    for transport in ("http", "sse"):
        mounted.update(_route_methods(served[transport]))
    assert set(declared) == set(mounted), (
        f"the file declares {sorted(declared)}, a server with authentication "
        f"mounts {sorted(mounted)}"
    )
    assert _route_methods(served["streamable-http"]) == _route_methods(
        served["http"]
    ), "the file gives http and streamable-http one interface"
    for path, interface in declared.items():
        if "methods" in interface:
            assert set(interface["methods"]) == mounted[path], (
                f"{path}: the file says {sorted(interface['methods'])}, the server "
                f"answers {sorted(mounted[path])}"
            )
    metadata_paths = set(_paths(interfaces[_METADATA_INTERFACE]))
    assert _routes("http") | _routes("sse") == set(declared) - metadata_paths, (
        "the assembled server mounts every declared path but the sign-in "
        "document, which needs authentication configured"
    )
    guide = _DEPLOYMENT_GUIDE.read_text(encoding="utf-8")
    for path in metadata_paths:
        assert path.startswith("/.well-known/oauth-protected-resource/")
    assert "/.well-known/oauth-protected-resource/mcp" in guide, (
        "the deployment guide no longer shows the path it measured"
    )

    for transport in ("http", "sse"):
        app = served[transport]
        methods = _route_methods(app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            for path, interface in declared.items():
                if "GET" not in methods.get(path, set()):
                    continue
                response = await client.get(path)
                needs_token = interface["authentication"] != "none"
                assert (response.status_code == 401) == needs_token, (
                    f"GET {path} without a token answered {response.status_code} "
                    f"on {transport}; the file says authentication "
                    f"{interface['authentication']!r}"
                )

    listening = {
        (interface["host"], interface["port"])
        for interface in interfaces.values()
        if "host" in interface
    }
    assert listening == {
        (
            Settings.model_fields["mcp_host"].default,
            Settings.model_fields["mcp_port"].default,
        )
    }, (
        "the listen address is not the default of FINOS_MCP_MCP_HOST and FINOS_MCP_MCP_PORT"
    )


def test_every_interface_without_a_token_declares_its_exemption() -> None:
    """No interface id is excluded: each open one says where that is recorded.

    The health URLs are opened by the open-health-urls control and name it;
    the sign-in document, and stdio, name the document that records theirs.
    """
    architecture = _architecture()
    interfaces = _interfaces(_node(architecture, _SERVER))
    health = _control_config(architecture, _HEALTH_CONTROL)

    opened_by_control: set[str] = set()
    for unique_id, interface in interfaces.items():
        if interface["authentication"] != "none":
            assert "exemption" not in interface, f"{unique_id}: needs a token"
            continue
        exemption = interface.get("exemption", "")
        assert exemption.strip(), f"{unique_id}: served without a token, no exemption"
        if exemption == _HEALTH_CONTROL:
            opened_by_control.update(_paths(interface))
            continue
        recorded_in = re.search(
            r"\b(docs/[\w./-]+\.md)\b|\bexempt-transports\b", exemption
        )
        assert recorded_in, (
            f"{unique_id}: the exemption names no document: {exemption!r}"
        )
        if recorded_in.group(1):
            assert (_ROOT / recorded_in.group(1)).is_file(), recorded_in.group(1)
    assert set(health["paths"]) == opened_by_control == {"/healthz", "/readyz"}, (
        "the open-health-urls control and the interfaces that name it disagree "
        "on which paths it opens"
    )


async def test_the_authentication_control_names_the_claims_the_code_checks(
    key_pair: tuple[bytes, str],
) -> None:
    """``verified-claims`` holds what is checked whatever the settings (#324).

    ``iss`` and ``aud`` because ``validate_startup`` refuses a networked
    transport without them; ``exp`` and ``sub`` because the verifier refuses a
    token without them. ``scope`` is not among them: startup accepts no
    required scopes, and the verifier then requires none.
    """
    private_pem, public_pem = key_pair
    architecture = _architecture()
    authentication = _control_config(architecture, "authentication")
    always_checked: set[str] = set()

    for claim, field in (("iss", "mcp_auth_issuer"), ("aud", "mcp_auth_audience")):
        with pytest.raises(ValueError, match=f"{field} is required"):
            _authenticated_settings(public_pem, **{field: None}).validate_startup()
        always_checked.add(claim)

    without_scopes = _authenticated_settings(public_pem)
    without_scopes.validate_startup()
    verifier = _build_auth_provider(without_scopes)
    assert isinstance(verifier, jwt_verifier.FinosJWTVerifier)
    assert verifier.required_scopes == []
    with_scopes = _authenticated_settings(
        public_pem, mcp_auth_required_scopes="governance:read"
    )
    scoped = _build_auth_provider(with_scopes)
    assert isinstance(scoped, jwt_verifier.FinosJWTVerifier)
    assert scoped.required_scopes == ["governance:read"]
    assert authentication["scope-checked-when"] == "FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES"

    assert await verifier.load_access_token(_token(private_pem)) is not None
    for claim in ("iss", "aud"):
        assert (
            await verifier.load_access_token(_token(private_pem, **{claim: "x"}))
            is None
        )
    for claim in ("exp", "sub"):
        assert (
            await verifier.load_access_token(_token(private_pem, **{claim: None}))
            is None
        )
        always_checked.add(claim)
    assert set(authentication["verified-claims"]) == always_checked

    # The JWKS sentences: the interval is this server's, the hour is fastmcp's
    # key cache, which the sentence describes.
    jwks = _interfaces(_node(architecture, "authorization-server"))["jwks"]
    keys = _relationship(architecture, "server-fetches-signing-keys")
    for text in (jwks["description"], keys["description"]):
        interval = re.search(r"at most once in (\d+) seconds", text)
        assert interval, f"no fetch interval in {text!r}"
        assert float(interval.group(1)) == jwt_verifier.JWKS_FETCH_INTERVAL_SECONDS
        assert "older than an hour" in text
    assert verifier._cache_ttl == 3600  # pylint: disable=protected-access


def test_the_numbers_in_the_descriptions_are_the_codes() -> None:
    """A default or a limit a sentence states is read out of it and compared."""
    architecture = _architecture()

    probe = _relationship(architecture, "server-fetches-documents")["description"]
    found = re.search(
        r"probes (\S+) there .*?FINOS_MCP_READINESS_PROBE_INTERVAL_SECONDS "
        r"\((\d+) by default\)",
        probe,
    )
    assert found, f"no probe file and default interval in {probe!r}"
    assert found.group(1) == http_health._PROBE_FILE  # pylint: disable=protected-access
    assert int(found.group(2)) == (
        Settings.model_fields["readiness_probe_interval_seconds"].default
    )

    listing = _node(architecture, "discovery-list-file")["description"]
    limit = re.search(r"larger than (\d+) KiB", listing)
    assert limit, f"no size limit in {listing!r}"
    assert int(limit.group(1)) * 1024 == list_file.SIZE_LIMIT_BYTES
    mode = re.search(r"created (0[0-7]{3})", listing)
    assert mode, f"no directory mode in {listing!r}"
    assert f"mode=0o{mode.group(1)[1:]}" in inspect.getsource(
        list_file.resolve_directory
    )


async def test_the_outbound_hosts_are_the_ones_the_code_allows() -> None:
    architecture = _architecture()
    allowlist = _control_config(architecture, "outbound-host-allowlist")
    assert allowlist["default-hosts"] == sorted(_DEFAULT_FETCH_HOSTS), (
        "the allowlist in the file is not the one in content/fetch.py"
    )
    assert "security/content_filter.py" in allowlist["description"]
    assert (
        Path(content_filter.__file__).as_posix().endswith("security/content_filter.py")
    )
    assert content_filter.is_allowed_fetch_target(
        "https://raw.githubusercontent.com/x", _DEFAULT_FETCH_HOSTS
    )
    assert allowlist["scheme"] == "https"
    assert not content_filter.is_allowed_fetch_target(
        "http://raw.githubusercontent.com/x", _DEFAULT_FETCH_HOSTS
    )
    client = HTTPClient(Settings())
    try:
        assert allowlist["redirects"] == "not followed"
        assert client._client.follow_redirects is False  # pylint: disable=protected-access
    finally:
        await client.close()

    default_url = urlparse(Settings.model_fields["base_url"].default)
    raw = _interfaces(_node(architecture, "content-host"))["raw-documents"]
    assert (raw["host"], raw["path"]) == (default_url.hostname, default_url.path), (
        "the content host interface is not the default FINOS_MCP_BASE_URL"
    )
    assert (
        raw["setting"] == allowlist["configured-host-setting"] == "FINOS_MCP_BASE_URL"
    )

    external_hosts = {
        node["unique-id"]: interface["host"]
        for node in architecture["nodes"]
        if node["unique-id"] != _SERVER
        for interface in node.get("interfaces", [])
        if "host" in interface
    }
    assert set(external_hosts.values()) == set(_DEFAULT_FETCH_HOSTS), (
        f"the external systems with a host are {external_hosts}; the content "
        f"client may reach {sorted(_DEFAULT_FETCH_HOSTS)}"
    )
    assert not any(
        "host" in interface
        for interface in _node(architecture, "authorization-server")["interfaces"]
    ), "the authorization server is named by setting, not by host"

    for relationship in architecture["relationships"]:
        ends = relationship["relationship-type"]["connects"]
        destination = _node(architecture, ends["destination"]["node"])
        if (
            ends["source"]["node"] == _SERVER
            and destination["unique-id"] in external_hosts
        ):
            assert relationship.get("protocol") == "HTTPS", (
                f"{relationship['unique-id']}: the content client speaks HTTPS only"
            )


def test_every_setting_the_file_names_exists() -> None:
    text = _ARCHITECTURE.read_text(encoding="utf-8")
    for schema in sorted(_CONTROLS.glob("*.json")):
        text += schema.read_text(encoding="utf-8")
    named = set(_SETTING.findall(text))
    assert len(named) >= 10, f"only {len(named)} settings are named: {sorted(named)}"

    prefix = Settings.model_config["env_prefix"]
    fields = {f"{prefix}{name.upper()}" for name in Settings.model_fields}
    fields.add(ENV_FILE_VARIABLE)  # read before the settings, not one of them
    unknown = sorted(named - fields)
    assert not unknown, f"the file names settings the server does not have: {unknown}"


def test_the_static_catalog_names_the_lists_the_code_holds() -> None:
    architecture = _architecture()
    lists = _interfaces(_node(architecture, "static-catalog"))["static-lists"]
    assert (_ROOT / lists["module"]).resolve() == Path(
        static_catalog.__file__
    ).resolve(), f"{lists['module']} is not the static catalog module"
    in_code = {
        name
        for name in dir(static_catalog)
        if name.startswith("STATIC_") and name.endswith("_FILES")
    }
    assert set(lists["names"]) == in_code, (
        f"the file names {sorted(lists['names'])}, the module holds {sorted(in_code)}"
    )
    for name in lists["names"]:
        files = getattr(static_catalog, name)
        assert files and all(isinstance(file, str) for file in files), (
            f"{name} is not a list of file names"
        )
