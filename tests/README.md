# macli tests

Two parallel test layers, both run from the repo root.

## 1. pytest unit tests

Pure-function unit tests for the helpers inside `macli` that don't touch
macOS subsystems (no `osascript`, no WeChat AX, no `npm`, no subprocesses).

```sh
pytest tests/ -v
```

Covered:

- `tests/test_envelope.py` — `_envelope`, `_has_flag`, `_parse_int_flag`
- `tests/test_auth.py` — `_is_auth_error` keyword matrix
- `tests/test_kb_search.py` — `_kb_parse_frontmatter`, `_kb_tokenize`,
  `_kb_score`, `_kb_newest_mtime`, plus end-to-end build/load index cycle
  driven by `tmp_path`
- `tests/test_constants.py` — `SCHEMA_VERSION`, `VERSION`,
  `_WX_FAIL_TITLES`, `X_INTERNAL`, `CACHE_DIR`, `CACHE_TTL`

`macli` is a Python file without a `.py` extension; the
`tests/conftest.py` fixture loads it via `importlib.util.spec_from_loader`
+ `SourceFileLoader` and yields it as the `macli` fixture so each test
gets the module for free.

No pip deps required beyond pytest itself. Tests do not shell out, do not
hit the network, and do not touch `~/.tx` (filesystem tests use
`tmp_path` and `monkeypatch.setattr` to rebind module globals).

## 2. Bash smoke tests

Black-box integration tests against the installed `macli` binary. They
verify well-formed `--json` envelopes for read-only commands.

```sh
./tests/test_smoke.sh                 # uses macli on PATH
MACLI=./macli ./tests/test_smoke.sh   # run against the repo copy
FAIL_FAST=1 ./tests/test_smoke.sh     # stop on first failure
```

Requires `jq` (`brew install jq`).

## Running both

```sh
pytest tests/ -v && MACLI=./macli ./tests/test_smoke.sh
```
