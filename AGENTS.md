# AGENTS.md — Agent Developer Guide for macos-cli

This file provides context for AI agents (Claude Code, Cursor, Codex, etc.) working in this repository.

## Project Overview

- **Project**: macos-cli — A unified macOS automation router. Binary is `macli`.
- **Three namespaces**: `macli x` (X/Twitter), `macli wx` (WeChat), `macli mac` (macOS apps + system)
- **Language**: Python 3.10+ (zero pip dependencies for the main `macli` file)
- **Platform**: macOS-only by design (AppleScript / Accessibility API / pyobjc)
- **Architecture**: Single-file CLI router (`macli`, ~2640 LOC) that fans out to 5 vendored backends.

## What This Project Is NOT

- **NOT a Python package** with `setup.py`. The `macli` file is a stand-alone executable Python script with a shebang.
- **NOT modular**. It's a deliberate single-file CLI. Don't suggest splitting into `cli.py + router.py + handlers.py`.
- **NOT cross-platform**. Half the commands require AppleScript / Accessibility / pyobjc. Don't suggest Linux/Windows support.
- **NOT pip-installable**. Users `./install.sh` to symlink the script into PATH.

## Hard Rules — Do Not Touch Without Explicit Request

| Path | Why hands-off |
|---|---|
| `vendor/*/` | Vendored upstream source. Patches go in via `cp` from external, not edits in place. Updating: see `vendor/UPSTREAM_PINS.md`. |
| `vendor/wechat-mcp/src/wechat_mcp/wechat_accessibility.py` | **Locally patched** (+283 lines vs upstream). Don't revert to upstream version — current WeChat UI requires this patch. See `vendor/wechat-mcp/PATCH_NOTES.md`. |
| `vendor/wechat-mcp/src/wechat_mcp/fetch_messages_by_chat_utils.py` | Same — locally patched (+89 lines). |
| `vendor/bird/` | Upstream GitHub repo was **deleted**. Only the npm package contents exist here. No source to refer to. Don't suggest rewrites. |
| `~/.tx/` | **User data directory** (cache, cookies, sqlite). Kept as `.tx` (not `.macli`) for backward compat with magpie-era users. Don't migrate without explicit user request. |
| `TX_DB` env var | Backward-compat name. Don't rename to `MACLI_DB`. |
| `# tx cookies — extracted from ...` header in `~/.tx/cookies.env` | Parsed by `_cookies_status()` regex. If you change format, update the regex. |
| `LICENSES/` | Each upstream's LICENSE preserved verbatim for compliance. Don't edit. |

## Build / Lint / Test

Three-layer test pyramid (all in `tests/`):

```bash
# Layer 1 — bash smoke against the binary (18 tests, ~3s)
MACLI=./macli ./tests/test_smoke.sh

# Layer 2 — pytest unit tests of pure functions (127 tests, <1s)
# (_envelope / _kb_parse_frontmatter / _kb_score / etc — implementation-level)
pytest tests/test_envelope.py tests/test_auth.py tests/test_kb_search.py tests/test_constants.py

# Layer 3 — pytest behavior tests via subprocess (48 tests, ~5s)
# (public CLI surface — discovery endpoints, --json envelopes, --help intercept;
#  these are what survive internal refactors)
pytest tests/test_cli_behavior.py tests/test_discovery.py

# All at once
pytest tests/ && MACLI=./macli ./tests/test_smoke.sh
```

When adding/modifying a command: layer 3 (behavior) is mandatory; layer 2 only if you add a new pure helper. After any change, both `pytest tests/` and `./tests/test_smoke.sh` must stay green.

## Code Style

- **Line length**: ~100 characters (no strict enforcement)
- **Python**: 3.10+, stdlib only — **no pip dependencies** in `macli`
- **Functions**: `snake_case`. Helpers prefixed with `_` (private).
- **Constants**: `UPPER_SNAKE_CASE` at module top.
- **Type hints**: Optional. Used pragmatically, not religiously.
- **Comments**: Sparse. Comments explain WHY, not WHAT.
- **Error handling**: `sys.exit(code)` with informative stderr messages; never bare `raise` unless catching.
- **Subprocess**: Use `subprocess.run(capture_output=True, text=True, timeout=N)`. Always pass `timeout` for safety.

## Project Structure

```
macos-cli/
├── macli                          # The CLI (single Python file, ~1200 LOC)
├── install.sh                     # Symlinks macli into PATH, builds vendored deps
├── README.md                      # User-facing docs
├── AGENTS.md                      # ← This file (developer guide for AI agents)
├── SKILL.md                       # Capability declaration for autonomous agents
├── SCHEMA.md                      # JSON output envelope contract
├── LICENSE                        # MIT for macos-cli wrapper
├── LICENSES/                      # Original LICENSE files of vendored projects
├── .gitignore
└── vendor/                        # Vendored upstream sources (~32 MB)
    ├── bird/                      # X/Twitter GraphQL (npm package, upstream deleted)
    ├── twitter-cli/               # X primary backend (TLS impersonation)
    ├── opencli/                   # 132 web sites + browser bridge
    ├── macos-automator-mcp/       # 492 AppleScript snippets (KB only)
    ├── wechat-mcp/                # WeChat (locally patched)
    └── UPSTREAM_PINS.md           # Records each vendor's source commit
```

## File Layout of `macli`

The single file is organized top-down in sections by namespace. Don't trust hard-coded line numbers (they drift); navigate with grep:

```bash
grep -nE "^# =+$" macli            # major section dividers
grep -nE "^def cmd_" macli         # all command implementations
grep -nE "^def route" macli        # routers (route, route_x, route_wechat, route_mac)
grep -nE "^def _emit|^def _pop|^CMD_INFO|^ERROR_CODES" macli  # discovery/envelope infrastructure
```

Section order:

1. Module docstring + imports + constants (`CACHE_DIR`, vendor paths, `VERSION`, `SCHEMA_VERSION`)
2. Generic helpers (`_run`, `osascript`, `exec_or_fail`, `_envelope`, `_print_json`, `_pop_flag`, `_emit_ok`, `_emit_err`, `_notify_user`)
3. Self-describing registry (`NAMESPACES`, `INTERNAL_COMMANDS`, `ERROR_CODES`, `CMD_INFO`, `_emit_subcommand_help`, `_emit_namespace_listing`)
4. X subsystem (cookies / cache / cmd_x_* / route_x — absorbed from magpie 0.3 in v0.2)
5. WeChat subsystem (`_wechat_python` / `_wx_stage_and_send` / `_wx_verify_last_message` / `_wx_send_record` / cmd_wx_* / route_wechat)
6. macOS subsystem (`_kb_index` / `_kb_*_search_index` / cmd_mac_* / route_mac)
7. Top-level (cmd_doctor with `--fix` / cmd_stats / cmd_help / route / main)

## Routing Decisions

- **Namespaces**: `x` / `twitter` → route_x; `wx` / `wechat` → route_wechat; `mac` / `macos` → route_mac.
- **Legacy fallback**: anything not matching a namespace falls through to `route_x([head] + rest)` (magpie compat).
- **X dispatcher (route_x)**: After global flag stripping, dispatches to:
  - Internal X commands: `auth`, `archive`, `cookies-save`, `download`, `help`
  - `bird` / `twitter-cli` escape hatches
  - `--via bird|twitter-cli|opencli` forced backend
  - Site adapters (e.g., `arxiv`, `hackernews`)
  - Auto-route by command-name lookup: priority **twitter-cli > bird > opencli**

## Common Tasks for Agents

### Add a new `macli mac <subcommand>` (or wx/x subcommand — same 6-step pattern)

The CLI is self-describing — adding a command means **6 coordinated edits**, not just dispatching:

1. **Write `cmd_mac_foo(args)`** in the macOS section. First two lines should always be:
   ```python
   def cmd_mac_foo(args):
       as_json, args = _pop_flag(args, "--json")
       ...
   ```
   For envelope output: **use `_emit_ok(data)` and `_emit_err(code, message, data=None)`**, NEVER raw `_print_json(_envelope(...))`. The helpers exist precisely so call sites stay one-liners and a future envelope-shape change is a one-place edit.

2. **Register in the namespace's subcommand list** (so `macli mac --json` discovery sees it):
   ```python
   MAC_SUBCOMMANDS = ["kb", "kb-list", "kb-search", "script", "dark-mode", "volume", "foo"]
   ```

3. **Add the dispatch line** in `route_mac()`:
   ```python
   if sub == "foo":  return cmd_mac_foo(rest)
   ```

4. **Add a `CMD_INFO` entry** keyed by full path (`"mac foo"`) — without this, `macli help mac foo --json` returns `not_found` and the discovery test pyramid fails:
   ```python
   "mac foo": {
       "synopsis": "macli mac foo <arg> [--flag] [--json]",
       "summary": "One-line description for agent discovery.",
       "behavior": [
           "Non-obvious contract 1 (the kind --help text doesn't say)",
           ...
       ],
       "see_also": ["mac script"],
   },
   ```

5. **Add behavior tests** in `tests/test_cli_behavior.py` (envelope shape, exit codes) and add a parametrized line in `tests/test_discovery.py::test_help_per_command_json_has_contract` for the new `"mac foo"` path. This pins the contract — refactor that breaks it surfaces immediately.

6. **Verify all three test layers pass**:
   ```bash
   pytest tests/ -q && MACLI=./macli ./tests/test_smoke.sh
   ```

The `--help` flag for the new command works automatically — `route_mac` already intercepts `--help` and dispatches to `_emit_subcommand_help("mac foo", ...)`, which reads from `CMD_INFO`. **That's why step 4 is mandatory: skipping it breaks `macli mac foo --help` AND `macli help mac foo --json` at once.**

### Add a new X command

Usually NOT needed — let the existing routing handle it. The auto-discovery (`build_cache`) picks up new commands from upstream `twitter-cli` / `bird` / `opencli` automatically when `macli --refresh` runs.

### Patch wechat-mcp

`vendor/wechat-mcp/src/wechat_mcp/*.py` IS the source of truth (vendored + locally patched). `vendor/wechat-mcp/.venv/` is built editable, so changes to source apply live without reinstall:

1. Edit files in `vendor/wechat-mcp/src/wechat_mcp/` directly (they're already the patched source)
2. Test by running `macli wx send ...` — the venv's `pip install -e` means edits take effect immediately
3. If you accidentally broke the venv (e.g. requirement bump), rebuild with `./macli doctor --fix` (auto-detects python3.13/3.12 and rebuilds at `vendor/wechat-mcp/.venv/`)
4. Update `vendor/wechat-mcp/PATCH_NOTES.md` with what changed vs the pinned upstream commit

### Update a vendored upstream

See `vendor/UPSTREAM_PINS.md` for upstream URL + commit pinned. To update:
1. `git clone <url> /tmp/<name>`
2. `git -C /tmp/<name> checkout <new-commit>`
3. `cp -R /tmp/<name>/<source-tree>/* vendor/<name>/` (overlay)
4. For wechat-mcp: re-apply patches over upstream files
5. Bump pin in `vendor/UPSTREAM_PINS.md`
6. Test affected commands

## Critical Invariants

**Existing contracts (don't break)**:
- `macli x ...` MUST keep working with existing `~/.tx/` data (cache, cookies, bookmarks.db).
- `macli wx send` MUST stage clipboard via wechat-mcp's venv Python (pyobjc requirement), then paste via osascript.
- `--json` output MUST follow the envelope in `SCHEMA.md` (canonical: `macli help schema --json`). Don't print arbitrary JSON without the wrapper.
- `exec_or_fail()` is preferred over `subprocess.run()` when the rest of execution is irrelevant (zero-overhead handoff).
- Add hint messages to error paths — agents reading stderr should know what to do next.

**v0.4 self-describing contracts (introduced when slimming SKILL.md)**:
- Every envelope-emitting command MUST use `_emit_ok` / `_emit_err` helpers. Raw `_print_json(_envelope(...))` calls are forbidden outside of those two helpers' definitions (`grep -nE '_print_json\(_envelope\(' macli` should return exactly 2 hits — the helpers themselves).
- Every internal command path (`<ns> <sub>` or top-level like `doctor`/`stats`) MUST have a `CMD_INFO` entry. Discovery test `test_help_per_command_json_has_contract` parametrizes over this dict; a missing entry breaks `macli help <cmd> --json` AND the test simultaneously.
- Every router (`route_x` / `route_wechat` / `route_mac`) MUST handle standalone `--json` (returns subcommand listing) and intercept `--help` BEFORE dispatching to `cmd_*`. Otherwise `--help` gets passed as a positional and bugs like "treats --help as kb-search query" reappear.
- `cmd_wx_send` MUST call `_wx_send_record(...)` on every exit path (success and failure). This writes `~/.tx/wx_send.log` (NDJSON, append-only) and fires a `_notify_user(...)` desktop banner when `sys.stdout.isatty()` is False. Removing either of those silently regresses cron/agent visibility — caught by behavior tests only if you exercise non-TTY paths.

## Where to Look First

| Question | Where |
|---|---|
| What does `macli x archive` do? | `grep -n "^def cmd_x_archive" macli` |
| How are cookies extracted? | `grep -n "_extract_cookies_via_provider\|cmd_x_cookies_save" macli` |
| How is WeChat chat navigation done? | `vendor/wechat-mcp/src/wechat_mcp/wechat_accessibility.py:open_chat_for_contact()` |
| What KB scripts are available? | `macli mac kb-search "<intent>" --json` (preferred) or `macli mac kb-list --json` |
| What X commands does `bird` have? | `macli x help --json \| jq .data.bird` |
| Which internal commands exist (and their contracts)? | `macli help --json \| jq .data.commands`, then `macli help <cmd> --json` |
| What error codes can appear in envelopes? | `macli help errors --json` (canonical: the `ERROR_CODES` dict in `macli`) |
| What's the JSON envelope shape? | `macli help schema --json` (or SCHEMA.md) |
| When adding a new command — where does its metadata go? | `CMD_INFO` dict in `macli` (grep `CMD_INFO = {`) |
| What changed in the latest release? | `README.md` Changelog section |

Prefer self-describing CLI introspection over reading source — the CLI is the source of truth, and the test suite (`tests/test_discovery.py`) pins it.

## Anti-Patterns

- ❌ Adding pip dependencies to `macli` itself (vendor stays self-contained, main file stays stdlib-only)
- ❌ Splitting `macli` into multiple Python files
- ❌ Renaming `~/.tx/` to `~/.macli/` without migration logic
- ❌ Calling MCP servers (wechat-mcp, macos-automator-mcp) via JSON-RPC — we bypass MCP layer and use library imports / `osascript` directly
- ❌ Adding shell expansion in subprocess (always pass arg list, never `shell=True`)
- ❌ Editing `vendor/` files directly without overlay strategy

## License

MIT (see `LICENSE`). Each vendored project retains its own LICENSE in `vendor/<name>/LICENSE` and a copy in `LICENSES/`.
