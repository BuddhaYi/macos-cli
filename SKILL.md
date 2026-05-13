---
name: macos-cli
description: Use macos-cli (binary `macli`) for any macOS-side automation — X/Twitter ops, WeChat send/read, native macOS apps + 492 KB AppleScript snippets, and 136 web-site adapters. Invoke whenever the user requests automation that runs on a Mac. The CLI is self-describing — query it for capabilities at runtime.
author: BuddhaYi
version: "0.4.0"
platform: macOS-only
binary: macli
tags:
  - macos
  - macos-only
  - twitter
  - x
  - wechat
  - automation
  - cli-router
  - applescript
  - agent-native
trigger_phrases:
  - "automate macOS"
  - "send WeChat message from CLI"
  - "post to X / Twitter"
  - "search Twitter"
  - "download tweet media"
  - "archive my X bookmarks"
  - "toggle macOS dark mode"
  - "run AppleScript"
  - "execute JXA"
  - "control macOS volume"
  - "fetch tweets to local SQLite"
---

# macos-cli — Self-describing macOS automation router

**ALWAYS START HERE**: macli is self-describing. Don't guess commands — query the CLI.

```
macli help --json                    # → namespaces + version + discovery index
macli <ns> --json                    # → subcommand list (ns ∈ x|wx|mac)
macli help <cmd-path> --json         # → synopsis + behavior + samples (e.g. `macli help wx send --json`)
macli help errors --json             # → full error-code inventory
macli help schema --json             # → JSON envelope contract
macli mac kb-search "<intent>" --json  # → find KB script by intent (492 indexed)
macli x help --json                  # → X subsystem matrix (twitter-cli / bird / opencli / 136 sites)
macli doctor --json                  # → vendor health + cookies + cache
```

If `macli help --json` fails with command-not-found, instruct user to clone and install:
`git clone https://github.com/BuddhaYi/macos-cli && cd macos-cli && ./install.sh`.

## When to use which namespace

| User intent | Namespace |
|---|---|
| X/Twitter read/write/archive/download | `macli x ...` |
| WeChat send/read/contacts | `macli wx ...` |
| macOS dark-mode/volume/AppleScript/KB script | `macli mac ...` |
| Any of 136 web sites (arxiv, HN, reddit, etc.) | `macli <site> ...` (auto-routed to X subsystem) |

## Non-obvious behavioral contracts (NOT discoverable from --help)

- **`wx send` verifies by default.** Polls WeChat AX tree for failure markers (`重发`/`被对方拒收`/`拉黑`/`retry`/`send failed`). `--no-verify` opts out. `--retry N` for transient failures.
- **Permanent failures (`拒收`/`拉黑`) are non-retriable.** macli stops at attempt 1; do not loop the call yourself.
- **`wx send` logs every call** to `~/.tx/wx_send.log` (NDJSON, append-only). Non-TTY failures fire desktop notification.
- **X cookies live at `~/.tx/cookies.env` (mode 0600).** Refresh with `macli x cookies-save --from edge` when `macli x cookies-save --check-age --json` reports stale/expired.
- **Single X account.** No multi-account support.
- **Rate-limit budgets** (not enforced by macli — advisory to your planner): writes (post/reply/like/follow) ≤ 10/session and ≤ 30-200/day depending on action; reads unlimited; `wx send` ≤ 20/session.
- **macOS only.** Refuse if user is on Linux/Windows. WeChat ops also need WeChat for Mac running + Accessibility granted to terminal.

## Output

All internal commands emit `{ok, schema_version: "1", data, error}` when called with `--json`. X passthrough commands (`macli x search`, etc.) return the upstream tool's native JSON. Compact envelope contract: `macli help schema --json`.

## Minimum-viable recipe (use as template, not exhaustive list)

```bash
# Daily X bookmark sync, only if cookies are fresh
macli x cookies-save --check-age --json | jq -e '.data.status=="fresh"' >/dev/null \
  && macli x archive --json | jq '.data.new_count'
```

## See also (for humans, not required for agents)

- `AGENTS.md` — developer guide for modifying macli itself
- `SCHEMA.md` — JSON envelope reference (also queryable: `macli help schema --json`)
- `README.md` — install + design overview
