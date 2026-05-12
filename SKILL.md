---
name: macos-cli
description: Use macos-cli (binary `macli`) for any macOS-side automation — X/Twitter ops, WeChat send/read, native macOS apps and system control, plus 132 web site adapters. Invoke whenever the user requests automation that runs on a Mac, including content posting, message sending, file/media handling, dark mode toggle, AppleScript execution, or Twitter archive sync.
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

# macos-cli — Unified macOS Automation Router

**Binary:** `macli`
**Platform:** macOS only (requires AppleScript / Accessibility API)
**Architecture:** Single Python file + 5 vendored backends (no MCP server required; vendor source is in the repo)

## When to use this tool

| User intent | Subcommand |
|---|---|
| Any X/Twitter operation (read, post, like, follow, archive, download) | `macli x ...` |
| Send WeChat message (text or file) | `macli wx send <contact> <payload>` |
| Read WeChat history | `macli wx read <contact>` |
| Toggle macOS dark mode | `macli mac dark-mode <on\|off\|toggle>` |
| Get/set macOS volume | `macli mac volume [N]` |
| Run arbitrary AppleScript | `macli mac script '<code>'` |
| Use a pre-made KB script (492 available) | `macli mac kb <id> [args]` |
| Access any of 132 web sites (arxiv, HN, etc.) | `macli arxiv search "..."` or `macli x arxiv ...` |

## Setup

```bash
# Clone + install
git clone https://github.com/BuddhaYi/macos-cli.git
cd macos-cli
./install.sh

# Verify
macli doctor
```

Requirements: macOS, Python ≥ 3.10, Node ≥ 18, npm, pipx-or-uv.

## Authentication

### X / Twitter (`macli x ...`)

**Step 0 — check current state:**

```bash
macli x cookies-save --check-age      # exits 0 if fresh, 2 if stale, 1 if missing
```

**Step 1 — if cookies missing or stale, guide user:**

1. Tell user: "Open Edge Beta (preferred — no Safari ITP) → log in to x.com."
2. Run: `macli x cookies-save` (extracts via macOS Keychain; may prompt once).
3. Verify: `macli x auth`

Edge Beta is preferred because Safari ITP deletes cookies after 7-30 days; Edge cookies last ~13 months. Other supported sources: `--from chrome|safari|firefox|edge-stable`.

### WeChat (`macli wx ...`)

Requires:
- WeChat for macOS app installed AND running
- macOS Accessibility permission granted to your terminal (`System Settings → Privacy & Security → Accessibility`)
- User logged into WeChat

No explicit auth step — uses the live WeChat session.

### macOS (`macli mac ...`)

No auth. Some scripts require app-specific permissions (e.g., AppleScript access to Music, Mail). macOS will prompt on first use.

## Output Formats

### Default: Human-readable

```bash
macli doctor                          # Pretty tree
macli mac volume                      # Just "50"
macli wx send 老婆 "hi"                # "✓ sent text → 老婆"
```

### `--json`: Machine envelope (agent-friendly)

All commands documented in [SCHEMA.md](./SCHEMA.md) emit:

```yaml
ok: true
schema_version: "1"
data: <payload>
```

or on error:

```yaml
ok: false
schema_version: "1"
error:
  code: <machine_code>
  message: <human_message>
```

### X-subsystem outputs

`macli x ...` delegates to `twitter-cli` / `bird` / `opencli`. These tools each have their own native JSON output. `macli x` is execvp-passthrough so the upstream's JSON is what you get.

```bash
macli x search "AI" --json | jq '.data[].text'
macli x user-posts elonmusk --json
```

## Frequency / Rate-limit Budgets

X has hard rate limits (~400 writes/day, much lower for new accounts).

| Operation | Per-session budget | Per-day budget |
|---|---|---|
| `macli x like <url>` | ≤ 30 | ≤ 200 |
| `macli x post "..."` | ≤ 10 | ≤ 30 |
| `macli x follow <user>` | ≤ 10 | ≤ 50 |
| `macli x reply <url> "..."` | ≤ 20 | ≤ 100 |
| `macli x search "..."` | unlimited | unlimited |
| `macli x archive` | 1/run | 1-4/day |
| `macli wx send <contact> ...` | ≤ 20 | ≤ 100 |
| `macli mac *` | unlimited | unlimited |

If approaching limits, surface a warning and pause.

## Command Reference

### X / Twitter (`macli x ...`)

```bash
# Reads (no rate-limit concerns)
macli x search "Claude Code" --max 10 --json
macli x home --json
macli x user-posts elonmusk --max 20
macli x bookmarks --json
macli x mentions
macli x news                              # AI-curated Explore content (bird only)
macli x about <handle>                    # account origin (bird only)
macli x whoami

# Writes (mind the budgets above)
macli x post "..." [--image PATH]
macli x reply <url> "..."
macli x like <url>
macli x retweet <url>
macli x follow <handle>
macli x unfollow <handle>

# Internal
macli x archive                           # sync bookmarks → ~/.tx/bookmarks.db
macli x download --tweet-url <url> [--output DIR]   # max-bitrate video + orig images
macli x download <username> --limit 30 --output DIR
macli x cookies-save [--from edge|chrome|safari|firefox|edge-stable]
macli x cookies-save --check-age
macli x auth                              # 3-backend health check
macli x doctor

# Site adapters (132 sites via opencli)
macli arxiv search "transformer"
macli hackernews top
macli reddit search "..." 
macli xiaohongshu feed
```

### WeChat (`macli wx ...`)

```bash
# Text
macli wx send 老婆 "下班来接我"

# File (auto-detected by Path.is_file)
macli wx send 老婆 ~/Downloads/合同.pdf
macli wx send 老婆 /tmp/screenshot.png

# Read last N messages
macli wx read 老婆 --limit 10            # JSON output by default for read
```

**Important**: file paths must be absolute or in CWD. Tilde-expansion is handled.

### macOS (`macli mac ...`)

```bash
# Run a custom AppleScript
macli mac script 'tell app "Music" to play'
macli mac script 'return name of current user'

# Use a pre-made KB script (492 available)
macli mac kb-list                           # show all script IDs
macli mac kb safari_get_front_tab_url
macli mac kb safari_save_as_pdf ~/page.pdf

# Built-in shortcuts
macli mac dark-mode <on|off|toggle>
macli mac volume                            # without arg = read
macli mac volume 50
```

## Agent Workflows

### Daily X bookmark sync (one-shot)

```bash
macli x cookies-save --check-age >/dev/null || macli x cookies-save
macli x archive --json | jq '.data.new_count'
```

### Search X then download all matching media

```bash
macli x search "AI walnut measurement" --max 5 --json | \
  jq -r '.data[].id' | \
  while read tid; do
    macli x download --tweet-id "$tid" --output ./dataset/
  done
```

### Send WeChat with confirmation read

```bash
macli wx send 老婆 "Test 1234"
sleep 3
macli wx read 老婆 --limit 1               # confirm last message
```

### Toggle dark mode, run a quick script

```bash
macli mac dark-mode on
macli mac script 'tell app "System Events" to set volume output muted of (get volume settings)'
```

### Use KB to get current Safari URL (no auth needed)

```bash
URL=$(macli mac kb safari_get_front_tab_url)
macli x search "$URL" --max 1 --json
```

## Error Reference

| Error | Cause | Fix |
|---|---|---|
| `tx wx: no wechat-mcp venv found` (legacy, now `macli wx: ...`) | Vendor not installed | `./install.sh` |
| `cookies likely expired` | X session invalidated | Re-login in Edge Beta → `macli x cookies-save` |
| `WeChat: could not navigate to 'X'` | WeChat AX tree changed OR contact name typo | Verify contact name in WeChat sidebar |
| `osascript: execution error: -1743` | Accessibility permission missing | Grant terminal in System Settings → Privacy → Accessibility |
| `bird bookmarks failed: HTTP 401` | Cookies expired | `macli x cookies-save` |
| `tx mac kb: id 'foo' not found` (legacy) | KB script name typo | `macli mac kb-list \| grep <part>` |

## Limitations

- **macOS only** — AppleScript / Accessibility / pyobjc requirements
- **WeChat for Mac required** — no iOS / Android / Web WeChat support
- **One X account at a time** — single cookie store at `~/.tx/cookies.env`
- **Single-user** — no multi-tenant; this is a personal tool
- **No CRX-style installable distribution** — clone + `./install.sh` is the only install path

## Safety Notes

- X writes have built-in 1.5-4s jitter (inherited from twitter-cli)
- WeChat operations use real browser-like UI events; account-safe for personal-volume use
- Cookies are stored at `~/.tx/cookies.env` with mode 0600
- `macli` itself never sends data anywhere except the explicit X/WeChat/macOS targets you invoke
- Agents should treat cookies and WeChat content as user-secret — don't echo to stdout / logs unnecessarily

## See Also

- [AGENTS.md](./AGENTS.md) — developer guide for AI agents modifying this repo
- [SCHEMA.md](./SCHEMA.md) — JSON output envelope contract
- [README.md](./README.md) — human-facing documentation
- [vendor/UPSTREAM_PINS.md](./vendor/UPSTREAM_PINS.md) — exact upstream sources
