# Configuration

```
config/
└── security/
    ├── bandit.yml    # bandit's rules for the Python security scan
    └── semgrep.yml   # semgrep's rules for the static analysis
```

Neither tool finds these files by itself: every call site passes the path. The
workflows, `scripts/ci-local.sh` and `.pre-commit-config.yaml` run, for example,
`bandit -c config/security/bandit.yml -r src/` and
`./scripts/semgrep-isolated.sh --config config/security/semgrep.yml src/`.

Every other tool reads `pyproject.toml` at the repository root:

| Tool | Section |
|---|---|
| mypy | `[tool.mypy]` |
| ruff | `[tool.ruff]` |
| pytest | `[tool.pytest.ini_options]` |
| coverage | `[tool.coverage.report]` |
| pylint | `[tool.pylint.main]` |
| pip-audit suppressions | `[tool.finos.pip-audit]` |

A second configuration file for one of these tools is drift: mypy, for one,
reads `.mypy.ini` ahead of `pyproject.toml`. `tests/unit/test_ci_config_drift.py`
fails the build if one appears. Pre-commit hooks live in
`.pre-commit-config.yaml`, and the workflows in `.github/workflows/`.
