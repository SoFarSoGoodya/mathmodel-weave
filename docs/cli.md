# CLI Reference

Use the project environment and inspect exact arguments with `--help`:

```text
uv run mmagent --help
uv run mmagent init CASE_DIR
uv run mmagent doctor CASE_DIR
uv run mmagent serve CASE_DIR
```

The normal lifecycle is init, evidence intake/correction, coordinator or command submission,
serve/poll, experiment preparation and execution, evidence freeze, publication build, immutable
staging, human approval, and export. Case paths are relative to the case root. Unsupported keys
fail explicitly; credentials never belong in JSON or TOML.

The module notes under `docs/modules/` describe contracts and Python entry points.
