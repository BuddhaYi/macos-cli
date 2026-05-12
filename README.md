# macos-cli 🍎

> Unified single-command CLI for macOS automation across X/Twitter, WeChat, and arbitrary native apps. All upstream dependencies **vendored** for offline reproducibility and immunity against upstream deletion.

```bash
macli x search "Claude Code"          # → vendor/magpie (twitter-cli + bird + opencli)
macli x archive                       # → vendor/magpie (SQLite incremental sync)
macli wx send 老婆 "下班来接"          # → vendor/wechat-mcp (locally patched)
macli wx send 老婆 ~/Downloads/x.pdf   # ↑ same, auto-detects file
macli mac dark-mode toggle            # → osascript
macli mac volume 50                   # → osascript
macli mac kb safari_save_as_pdf x.pdf # → vendor/macos-automator-mcp KB (492 scripts)
macli arxiv search "vision"           # → vendor/opencli arxiv adapter
```

One Python file (`macli`, ~1200 LOC, no pip deps) + 5 vendored backends = 39 MB self-contained repo.

> **v0.2 note**: this project absorbed [magpie](https://github.com/BuddhaYi/magpie)'s X-routing logic directly into `macli`. magpie as a runtime layer no longer exists — `macli x ...` calls the absorbed code, then execs `twitter-cli` / `bird` / `opencli` directly. See changelog below.

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
macli <namespace> <action> [args...]
       │
       ├─ macli x   ...  → twitter-cli / bird / opencli (X subsystem, absorbed from magpie in v0.2)
       ├─ macli wx  ...  → vendor/wechat-mcp Python lib (locally patched)
       ├─ macli mac ...  → vendor/macos-automator-mcp KB + osascript
       └─ <legacy> ...   → X subsystem (backward-compat passthrough)
```

### Vendored backends

| Path | Purpose | Source | LOC |
|---|---|---|---|
| `vendor/bird/` | X/Twitter via GraphQL (fallback for `mentions`/`news`/`about`) | `@steipete/bird@0.8.0` npm (upstream GitHub **deleted**) | compiled `dist/` |
| `vendor/twitter-cli/` | Primary X backend (TLS impersonation) | `public-clis/twitter-cli` | ~3 k Python |
| `vendor/opencli/` | 132 web sites + 8 app adapters + browser bridge | `jackwener/opencli` | ~17 MB TS |
| `vendor/macos-automator-mcp/` | 492 reusable AppleScript/JXA snippets (KB only used) | `steipete/macos-automator-mcp` | ~3 MB |
| `vendor/wechat-mcp/` | WeChat send/read via macOS Accessibility | `BiboyQG/WeChat-MCP` + **local patches** | ~2 k Python |

The X routing logic itself (originally a separate `vendor/magpie/tx` file) was absorbed into top-level `macli` in v0.2 — `magpie` no longer exists as a runtime layer. See `LICENSES/magpie-MIT.txt` for the original attribution.

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
3. Symlinks `macli` into your PATH

Requires: macOS, Python ≥ 3.10, Node ≥ 18, `npm`, `pipx` or `uv`.

---

## Usage

### X / Twitter (delegated to magpie)

```bash
macli x search "Claude Code" --max 5
macli x home --json | jq -r '.[].text'
macli x archive                            # sync bookmarks to ~/.tx/bookmarks.db
macli x download --tweet-url <url>         # max-quality video + orig images
macli x cookies-save                       # extract X cookies once
macli x auth                               # 3-backend health check
```

Everything magpie's X router supports works under `macli x ...` — the routing logic was inlined into `macli` in v0.2 (see Changelog).

### WeChat

```bash
macli wx send <contact> "<text>"           # send text
macli wx send <contact> <path-to-file>     # send file (auto-detects)
macli wx read <contact> --limit 10         # fetch recent messages (JSON)
```

WeChat for macOS must be running and logged in. macOS Accessibility permission must be granted to your terminal (`System Settings → Privacy & Security → Accessibility`).

### macOS

```bash
# 1. Inline AppleScript
macli mac script 'tell app "Music" to play'
macli mac script 'return name of current user'

# 2. Curated KB (492 pre-made scripts)
macli mac kb-list                          # show all available script ids
macli mac kb safari_get_front_tab_url      # run a KB script
macli mac kb mailmaster_move_emails 已删除 收件箱 "login to X" ""

# 3. Built-in shortcuts
macli mac dark-mode <on|off|toggle>
macli mac volume [0-100]                   # without arg = read current
```

---

## Where data lives

```
~/.tx/                          # magpie's data (created by macli x ...)
├── cache.json                  # X command discovery cache
├── cookies.env                 # X auth (mode 0600)
├── bookmarks.db                # SQLite archive
└── archive.log                 # launchd output
```

Nothing leaves your machine.

---

## Doctor

```bash
macli doctor
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
- `LICENSES/magpie-MIT.txt` (MIT — original magpie attribution, absorbed in v0.2)

---

## Changelog

### v0.2 — magpie absorbed
- The X routing logic (formerly `vendor/magpie/tx`) is now **inlined** into top-level `macli`. magpie repository is no longer a vendored runtime layer.
- `macli x ...` calls the absorbed code directly; one less Python process per X command (~50ms saved).
- `LICENSES/magpie-MIT.txt` preserves the original copyright attribution.
- Backward compat: legacy `macli search "..."` style commands still work (auto-routed to X subsystem).

### v0.1 — initial release
- Three namespaces: `macli x` (X/Twitter), `macli wx` (WeChat), `macli mac` (macOS).
- All upstream deps vendored for offline reproducibility.
- bird preserved from npm package (upstream GitHub deleted).
- wechat-mcp includes local patches for current WeChat UI.

---

## Credits

Built on top of (all vendored, see `vendor/UPSTREAM_PINS.md`):
- [magpie](https://github.com/BuddhaYi/magpie) — X routing logic (absorbed v0.2)
- [twitter-cli](https://github.com/public-clis/twitter-cli) by jackwener
- [bird](https://www.npmjs.com/package/@steipete/bird) by Peter Steinberger (GitHub deleted)
- [opencli](https://github.com/jackwener/opencli) by jackwener
- [macos-automator-mcp](https://github.com/steipete/macos-automator-mcp) by Peter Steinberger
- [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP) by Banghao Chi (locally patched)
