# macos-cli 🍎

> Unified single-command CLI for macOS automation across X/Twitter, WeChat, and arbitrary native apps. All upstream dependencies **vendored** for offline reproducibility and immunity against upstream deletion.

```bash
tx x search "Claude Code"          # → vendor/magpie (twitter-cli + bird + opencli)
tx x archive                       # → vendor/magpie (SQLite incremental sync)
tx wx send 老婆 "下班来接"          # → vendor/wechat-mcp (locally patched)
tx wx send 老婆 ~/Downloads/x.pdf   # ↑ same, auto-detects file
tx mac dark-mode toggle            # → osascript
tx mac volume 50                   # → osascript
tx mac kb safari_save_as_pdf x.pdf # → vendor/macos-automator-mcp KB (492 scripts)
tx arxiv search "vision"           # → vendor/opencli arxiv adapter
```

One Python file (`tx`, ~300 LOC) + 5 vendored backends = 38 MB self-contained repo.

---

## Why this exists

| Pain | Solution |
|---|---|
| `bird`'s GitHub repo was **deleted**; only the npm package remains. | Vendored as files in `vendor/bird/`. Immune to npm yanks. |
| `wechat-mcp` upstream is unmaintained and **broken** on current WeChat UI. | Vendored + **locally patched** (`wechat_accessibility.py`, `fetch_messages_by_chat_utils.py`). |
| Different MCP servers / npm packages / pipx tools / git repos — `clone && go` was impossible. | Single repo, one `./install.sh` builds everything. |
| Version drift breaking automation. | All deps pinned to specific commits (see `vendor/UPSTREAM_PINS.md`). |

---

## Architecture

```
tx <namespace> <action> [args...]
       │
       ├─ tx x   ...  → vendor/magpie/tx (already routes bird + twitter-cli + opencli)
       ├─ tx wx  ...  → vendor/wechat-mcp Python lib (locally patched)
       ├─ tx mac ...  → vendor/macos-automator-mcp KB + osascript
       └─ <legacy> ... → magpie (backward-compat passthrough)
```

### Vendored backends

| Path | Purpose | Source | LOC |
|---|---|---|---|
| `vendor/bird/` | X/Twitter via GraphQL (fallback for `mentions`/`news`/`about`) | `@steipete/bird@0.8.0` npm (upstream GitHub **deleted**) | compiled `dist/` |
| `vendor/twitter-cli/` | Primary X backend (TLS impersonation) | `public-clis/twitter-cli` | ~3 k Python |
| `vendor/opencli/` | 132 web sites + 8 app adapters + browser bridge | `jackwener/opencli` | ~17 MB TS |
| `vendor/macos-automator-mcp/` | 492 reusable AppleScript/JXA snippets (KB only used) | `steipete/macos-automator-mcp` | ~3 MB |
| `vendor/wechat-mcp/` | WeChat send/read via macOS Accessibility | `BiboyQG/WeChat-MCP` + **local patches** | ~2 k Python |
| `vendor/magpie/` | X router (single-file tx) | `BuddhaYi/magpie` | ~1 k Python |

See `vendor/UPSTREAM_PINS.md` for exact commit each was vendored from.

---

## Install

```bash
git clone https://github.com/<you>/macos-cli.git
cd macos-cli
./install.sh
```

`install.sh` does:
1. `npm link` each vendored Node package
2. `pipx install -e` each vendored Python package (editable, so patches stay)
3. Symlinks `tx` into your PATH

Requires: macOS, Python ≥ 3.10, Node ≥ 18, `npm`, `pipx` or `uv`.

---

## Usage

### X / Twitter (delegated to magpie)

```bash
tx x search "Claude Code" --max 5
tx x home --json | jq -r '.[].text'
tx x archive                            # sync bookmarks to ~/.tx/bookmarks.db
tx x download --tweet-url <url>         # max-quality video + orig images
tx x cookies-save                       # extract X cookies once
tx x auth                               # 3-backend health check
```

Everything `magpie` supports works under `tx x ...`. See `vendor/magpie/README.md`.

### WeChat

```bash
tx wx send <contact> "<text>"           # send text
tx wx send <contact> <path-to-file>     # send file (auto-detects)
tx wx read <contact> --limit 10         # fetch recent messages (JSON)
```

WeChat for macOS must be running and logged in. macOS Accessibility permission must be granted to your terminal (`System Settings → Privacy & Security → Accessibility`).

### macOS

```bash
# 1. Inline AppleScript
tx mac script 'tell app "Music" to play'
tx mac script 'return name of current user'

# 2. Curated KB (492 pre-made scripts)
tx mac kb-list                          # show all available script ids
tx mac kb safari_get_front_tab_url      # run a KB script
tx mac kb mailmaster_move_emails 已删除 收件箱 "login to X" ""

# 3. Built-in shortcuts
tx mac dark-mode <on|off|toggle>
tx mac volume [0-100]                   # without arg = read current
```

---

## Where data lives

```
~/.tx/                          # magpie's data (created by tx x ...)
├── cache.json                  # X command discovery cache
├── cookies.env                 # X auth (mode 0600)
├── bookmarks.db                # SQLite archive
└── archive.log                 # launchd output
```

Nothing leaves your machine.

---

## Doctor

```bash
tx doctor
```

Verifies all 6 vendored backends + 3 external CLIs (`bird`, `twitter`, `opencli`) are properly set up.

---

## License

MIT. Each vendored project retains its original LICENSE:

- `vendor/bird/LICENSE` (MIT)
- `vendor/opencli/LICENSE` (?)
- `vendor/macos-automator-mcp/LICENSE` (MIT)
- `vendor/twitter-cli/LICENSE` (MIT)
- `vendor/wechat-mcp/LICENSE` (MIT)
- `vendor/magpie/LICENSE` (MIT)

---

## Credits

Built on top of (all vendored, see `vendor/UPSTREAM_PINS.md`):
- [magpie](https://github.com/BuddhaYi/magpie) — X router
- [twitter-cli](https://github.com/public-clis/twitter-cli) by jackwener
- [bird](https://www.npmjs.com/package/@steipete/bird) by Peter Steinberger (GitHub deleted)
- [opencli](https://github.com/jackwener/opencli) by jackwener
- [macos-automator-mcp](https://github.com/steipete/macos-automator-mcp) by Peter Steinberger
- [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP) by Banghao Chi (locally patched)
