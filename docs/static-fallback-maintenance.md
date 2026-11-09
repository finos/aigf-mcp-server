# Built-in Catalog Maintenance Guide

## What the built-in catalog is

`src/finos_mcp/content/static_catalog.py` holds the names of the documents in
the three content directories of the FINOS AI Governance Framework repository,
as they were listed on the date the module records in `LISTED_ON`. The server
serves it, with `"source": "static_fallback"`, when it holds no list file for
the configured `FINOS_MCP_BASE_URL` and the GitHub API cannot be asked, or
cannot address that base URL (a host other than GitHub).

The module is generated. `scripts/update-static-fallback.py` writes it whole;
nothing in it is typed or copied by hand.

## The problem it guards against

When the catalog lags the repository:

- `list_risks()` names a document the repository no longer holds, and
  `get_risk(id)` on it fails with "could not be loaded"
- a document the repository added is not listed until GitHub can be asked

## Updating the catalog

**1. Run the script:**

```bash
python scripts/update-static-fallback.py
```

It lists the three directories through the GitHub API, refuses any name that
does not have the shape the corpus has (`ri-N_slug.md`, `mi-N_slug.md`,
`slug.yml`, lowercase), and writes `src/finos_mcp/content/static_catalog.py`
with today's date. When the module already holds the listing it writes nothing
and says so.

**2. Review the diff:**

```bash
git diff src/finos_mcp/content/static_catalog.py
```

Names only appear and disappear; a change to anything else means the module
was edited by hand, and the script has now put it right.

**3. Run the tests that read it:**

```bash
pytest tests/unit/test_static_catalog_module.py tests/integration/test_static_fallback_sync.py -q --no-cov
```

The first holds the shipped module to what the script renders; the second
compares it with the live listing and needs the network.

**4. Commit:**

```bash
git add src/finos_mcp/content/static_catalog.py
git commit -m "fix(service): regenerate the built-in catalog from the repository"
```

## When an update is due

`.github/workflows/validate-static-fallback.yml` runs
`tests/integration/test_static_fallback_sync.py` every Monday, on a push to
`main` that changes `src/finos_mcp/content/static_catalog.py`, and on manual
dispatch. A scheduled run that finds a difference opens an issue labelled
`static-fallback-sync` and points here.

Before a release, run the sync test once.

## Troubleshooting

### "GitHub API request failed"

The line names the cause. The script and the sync test ask the GitHub API
directly; the server's list file (`github_discovery.json` in its cache
directory) is neither read nor written, so there is nothing to clear first.

- `GitHubRateLimitError`: wait for the limit to reset (up to an hour), or set
  `FINOS_MCP_GITHUB_TOKEN`.
- A connection error or a timeout: the API could not be reached.
- `GitHubDiscoveryError` naming a status such as 404: GitHub answered, but not
  with a directory listing. Check `FINOS_MCP_BASE_URL`, then whether upstream
  moved the directory.

The sync test skips for the first two and fails for the third. In the weekly
workflow it fails for all three: the step passes the repository's
`GITHUB_TOKEN` as `FINOS_MCP_GITHUB_TOKEN` and sets `FINOS_STATIC_SYNC_NO_SKIP`,
under which an API that cannot be asked is a failure, so a run that compared
nothing cannot report the catalog synchronized.

### "The listing holds a name the catalog cannot carry"

The repository holds a file whose name is outside the shape above. The script
writes nothing. Look at the file in the repository: a name with a quote, a
capital letter or another extension is either a mistake upstream or a new
convention, and the rule in the script is where a new convention is admitted.

### `test_the_shipped_module_is_what_the_script_renders_from_its_own_lists` fails

The module was edited by hand, or formatted differently from the way the
script writes it. Run the script; it rewrites the module.

## Related files

- `src/finos_mcp/content/static_catalog.py`: the generated module
- `scripts/update-static-fallback.py`: writes it
- `tests/unit/test_static_catalog_module.py`: holds the module to the script
- `tests/integration/test_static_fallback_sync.py`: compares it with the live
  listing
- `tests/test_id_mapping.py`: checks the ids a listing publishes can be fetched;
  needs the network
