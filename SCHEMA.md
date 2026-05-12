# Structured Output Schema

`macli` uses a shared agent-friendly envelope for machine-readable output when invoked with `--json`.

## Envelope: Success

```yaml
ok: true
schema_version: "1"
data: <command-specific payload>
```

## Envelope: Error

```yaml
ok: false
schema_version: "1"
error:
  code: <machine_code>
  message: <human_readable_message>
```

## Standard Error Codes

- `invalid_args` — caller passed bad / missing args
- `not_found` — target (contact, tweet, kb script id) doesn't exist
- `not_authenticated` — cookies missing / expired
- `auth_check_failed` — cookies present but rejected by upstream
- `vendor_missing` — vendor/* path not set up (run `./install.sh`)
- `subprocess_failed` — underlying tool exited non-zero
- `timeout` — operation exceeded internal timeout
- `permission_denied` — macOS Accessibility / FDA / Keychain blocked
- `internal_error` — uncategorized

## Per-Command Schemas

### `macli doctor --json`

```yaml
ok: true
schema_version: "1"
data:
  version: "0.2.0"
  root: "/path/to/macos-cli"
  vendors:
    bird:                {path: "...", present: true}
    twitter-cli:         {path: "...", present: true}
    opencli:             {path: "...", present: true}
    macos-automator-mcp: {path: "...", present: true, kb_count: 492}
    wechat-mcp:          {path: "...", present: true}
  external_tools:
    bird:    "/Users/x/.npm-global/bin/bird"
    twitter: "/Users/x/.local/bin/twitter"
    opencli: "/Users/x/.npm-global/bin/opencli"
  x_cache:
    path: "~/.tx/cache.json"
    age_hours: 2.4
  cookies:
    source: "Edge Beta"
    age_days: 0.6
    status: "fresh"             # fresh|aging|stale (renew soon)|expired (renew NOW)|missing
```

### `macli help --json`

```yaml
ok: true
schema_version: "1"
data:
  version: "0.2.0"
  namespaces: ["x", "wx", "mac"]
  internal_commands: ["doctor", "help"]
```

### `macli wx send <contact> <payload> --json`

Success:
```yaml
ok: true
schema_version: "1"
data:
  contact: "老婆"
  kind: "text"                # text|file
  payload_preview: "下班来接我"
  sent_at: "2026-05-12T16:00:00"
```

Error (contact not found):
```yaml
ok: false
schema_version: "1"
error:
  code: not_found
  message: "could not navigate to '老婆'"
```

### `macli wx read <contact> --limit N --json`

```yaml
ok: true
schema_version: "1"
data:
  contact: "老婆"
  count: 10
  messages:
    - sender: "ME"
      text: "..."
    - sender: "老婆"
      text: "..."
```

### `macli mac script '<code>' --json`

```yaml
ok: true
schema_version: "1"
data:
  exit_code: 0
  stdout: "Hello from macOS"
  stderr: ""
```

Error (osascript fails):
```yaml
ok: false
schema_version: "1"
error:
  code: subprocess_failed
  message: "execution error: ... (-1743)"
data:
  exit_code: 1
  stdout: ""
  stderr: "execution error: ..."
```

### `macli mac dark-mode <on|off|toggle> --json`

```yaml
ok: true
schema_version: "1"
data:
  requested: "toggle"
  current: "on"               # final state after operation
```

### `macli mac volume [N] --json`

```yaml
ok: true
schema_version: "1"
data:
  volume: 50                  # current value (after set if N provided)
  changed: true               # false if read-only
```

### `macli mac kb <script-id> [args] --json`

```yaml
ok: true
schema_version: "1"
data:
  script_id: "safari_save_as_pdf"
  args: ["~/page.pdf"]
  exit_code: 0
  stdout: "..."
  stderr: ""
```

### `macli mac kb-list --json`

```yaml
ok: true
schema_version: "1"
data:
  count: 492
  scripts:
    - id: "safari_save_as_pdf"
      path: "02_browser/safari/safari_save_as_pdf.md"
    - id: "mail_get_unread_count"
      path: "01_apple_apps/mail/mail_get_unread_count.md"
    # ...
```

### `macli x archive --json`

```yaml
ok: true
schema_version: "1"
data:
  backend: "twitter-cli"      # which backend fetched (twitter-cli|bird)
  new_count: 3                # newly inserted rows
  total_count: 47             # total in db after sync
  db_path: "~/.tx/bookmarks.db"
```

Error (cookies expired):
```yaml
ok: false
schema_version: "1"
error:
  code: not_authenticated
  message: "cookies likely expired (95d old, from Edge Beta)"
data:
  backend: "twitter-cli"
  hint: "run: macli x cookies-save"
```

### `macli x cookies-save --check-age --json`

```yaml
ok: true
schema_version: "1"
data:
  source: "Edge Beta"
  age_days: 1.2
  status: "fresh"             # fresh|aging|stale|expired
```

### `macli x cookies-save --from <browser> --json`

```yaml
ok: true
schema_version: "1"
data:
  source: "Edge Beta"
  path: "~/.tx/cookies.env"
  mode: "0600"
```

## X-subsystem passthrough (`macli x <command>`)

When you run `macli x search ...` etc., the `macli x` dispatcher `execvp`s to `twitter-cli` / `bird` / `opencli` directly. The output you receive is **the upstream's native --json output**, not wrapped by macos-cli's envelope.

Refer to:
- `vendor/twitter-cli/SCHEMA.md` for twitter-cli's envelope (also `{ok, schema_version, data}`)
- bird `--json` and `--json-full` for bird-specific shapes
- opencli `--format json` for opencli outputs

For convenience, twitter-cli and macos-cli use a **compatible** envelope shape, so generic agent parsers work on both.

## Notes

- `--json` is opt-in. Default output is human-readable.
- For X-subsystem commands, `--json` is passed through to upstream tools transparently.
- Internal commands (`doctor`, `help`, `wx send/read`, `mac *`, `x archive`, `x cookies-save`, `x download`) implement the envelope themselves.
- Compact-mode flag (`-c` / `--compact`) is forwarded to twitter-cli when present; macos-cli internal commands ignore it.
- All `--json` writes go to **stdout**; logs / progress go to **stderr**. Pipes are safe (`macli ... --json | jq`).

## See Also

- [SKILL.md](./SKILL.md) — when to invoke macli and how to interpret outputs
- [AGENTS.md](./AGENTS.md) — developer guide for modifying macli itself
