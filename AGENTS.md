# AGENTS.md — Agent Developer Guide for macos-cli

This file provides context for AI agents (Claude Code, Cursor, Codex, etc.) working in this repository.

## Project Overview

- **Project**: macos-cli — A unified macOS automation router. Binary is `macli`.
- **Three namespaces**: `macli x` (X/Twitter), `macli wx` (WeChat), `macli mac` (macOS apps + system)
- **Language**: Python 3.10+ (zero pip dependencies for the main `macli` file)
- **Platform**: macOS-only by design (AppleScript / Accessibility API / pyobjc)
- **Architecture**: Single-file CLI router (`macli`, ~1200 LOC) that fans out to 5 vendored backends.

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

This project has **no formal test suite**. Verification is manual smoke testing.

```bash
# Make script executable (one-time)
chmod +x macli

# Run directly
./macli --version
./macli doctor

# Or via PATH symlink (after install.sh)
macli --help
```

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

The single `macli` file is organized in sections by namespace:

```
Lines 1-50    : Module docstring, imports, constants (CACHE_DIR, paths)
Lines 50-90   : Generic helpers (_run, osascript, exec_or_fail, suggest_similar)
Lines 90-820  : X subsystem (absorbed from magpie 0.3 in v0.2)
                - parse_*_cmds() — discovery parsers
                - build_cache() / load_cache()
                - cookies, config helpers
                - cmd_x_help / cmd_x_auth / cmd_x_archive / cmd_x_download / cmd_x_cookies_save
                - route_x() — X dispatcher
Lines 820-880 : WeChat subsystem (delegates to vendor/wechat-mcp venv Python)
                - _wechat_python() — finds venv
                - cmd_wx_send / cmd_wx_read
                - route_wechat()
Lines 880-980 : macOS subsystem (osascript + KB)
                - _kb_index() — parse vendor/macos-automator-mcp KB
                - cmd_mac_kb / cmd_mac_kb_list / cmd_mac_script / cmd_mac_dark_mode / cmd_mac_volume
                - route_mac()
Lines 980-1200: Top-level router
                - cmd_doctor / cmd_help
                - route() — main dispatcher
                - main() / __main__
```

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

### Add a new `macli mac <subcommand>`

1. Write `cmd_mac_foo(args)` function in the macOS section
2. Add a `if sub == "foo": return cmd_mac_foo(rest)` line in `route_mac()`
3. Update `cmd_help()` if user-facing
4. Add `--json` envelope output if appropriate (see SCHEMA.md)

### Add a new X command

Usually NOT needed — let the existing routing handle it. The auto-discovery (`build_cache`) picks up new commands from upstream `twitter-cli` / `bird` / `opencli` automatically when `macli --refresh` runs.

### Patch wechat-mcp

Don't edit `vendor/wechat-mcp/` directly. Instead:
1. Edit `~/.local/share/mcp-servers/wechat-mcp/.venv/lib/python3.12/site-packages/wechat_mcp/*.py` (the live install)
2. Test by running `macli wx send ...`
3. Once stable: `cp` the patched files into `vendor/wechat-mcp/src/wechat_mcp/`
4. Update `vendor/wechat-mcp/PATCH_NOTES.md` with what changed

### Update a vendored upstream

See `vendor/UPSTREAM_PINS.md` for upstream URL + commit pinned. To update:
1. `git clone <url> /tmp/<name>`
2. `git -C /tmp/<name> checkout <new-commit>`
3. `cp -R /tmp/<name>/<source-tree>/* vendor/<name>/` (overlay)
4. For wechat-mcp: re-apply patches over upstream files
5. Bump pin in `vendor/UPSTREAM_PINS.md`
6. Test affected commands

## Critical Invariants

- `macli x ...` MUST keep working with existing `~/.tx/` data (cache, cookies, bookmarks.db).
- `macli wx send` MUST stage clipboard via wechat-mcp's venv Python (pyobjc requirement), then paste via osascript.
- `--json` output MUST follow the envelope in `SCHEMA.md`. Don't print arbitrary JSON without the wrapper.
- `exec_or_fail()` is preferred over `subprocess.run()` when the rest of execution is irrelevant (zero-overhead handoff).
- Add hint messages to error paths — agents reading stderr should know what to do next.

## Where to Look First

| Question | File / Line |
|---|---|
| What does `macli x archive` do? | `macli:cmd_x_archive()` |
| How are cookies extracted? | `macli:_extract_cookies_via_provider()`, `cmd_x_cookies_save()` |
| How is WeChat chat navigation done? | `vendor/wechat-mcp/src/wechat_mcp/wechat_accessibility.py:open_chat_for_contact()` |
| What KB scripts are available? | `vendor/macos-automator-mcp/knowledge_base/` (~492 markdown files) |
| What X commands does `bird` have? | `~/.tx/cache.json` after `macli x --refresh` |

## Anti-Patterns

- ❌ Adding pip dependencies to `macli` itself (vendor stays self-contained, main file stays stdlib-only)
- ❌ Splitting `macli` into multiple Python files
- ❌ Renaming `~/.tx/` to `~/.macli/` without migration logic
- ❌ Calling MCP servers (wechat-mcp, macos-automator-mcp) via JSON-RPC — we bypass MCP layer and use library imports / `osascript` directly
- ❌ Adding shell expansion in subprocess (always pass arg list, never `shell=True`)
- ❌ Editing `vendor/` files directly without overlay strategy

## License

MIT (see `LICENSE`). Each vendored project retains its own LICENSE in `vendor/<name>/LICENSE` and a copy in `LICENSES/`.
