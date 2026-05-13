# Verifying WeChat sends in 2026: why fire-and-forget isn't enough for AI agents

> Or: how a $0 TDD skill caught a $silent-but-real bug my unit tests had been
> happily ignoring for six months.

A few weeks ago I noticed my Mac was running a daily cron that sent a status
update to me via WeChat. The cron exit code was 0. The agent that triggered it
reported "delivered." My phone had nothing.

I assumed the cron was broken. I tested it manually:

```bash
$ macli wx send 文件传输助手 "test"
{"ok": true, "schema_version": "1", "data": {"sent_at": "2026-05-12T22:00:00"}}
$ echo "exit: $?"
exit: 0
```

WeChat for Mac, open in the background, showed the test message had arrived.
The phone synced it within a second. So that case worked.

I then tested a contact who I knew had blocked me months ago:

```bash
$ macli wx send 张量观察tensorscan "test"
{"ok": true, "schema_version": "1", "data": {"sent_at": "..."}}
```

Same envelope. `ok: true`. Same exit code 0. **But this time the message was
never delivered** — WeChat had silently appended a system row to that chat
saying「消息已发出，但被对方拒收了」(message sent, rejected by recipient).

My CLI was lying to its caller.

## The shape of the lie

`macli wx send` does three steps:

1. **Stage**: pyobjc copies the payload to `NSPasteboard` (text or `NSURL`
   for files)
2. **Navigate**: wechat-mcp's `open_chat_for_contact(name)` walks the macOS
   Accessibility tree to find and click the chat row
3. **Send**: an AppleScript fires `Cmd+V` then `Return` via System Events

That's it. Then the function returned `{ok: true, sent_at: now()}`. There
was no step 4. After Return was pressed, control returned to Python, and
Python had no idea what WeChat had done with the keypress.

For 99% of sends — texts to active contacts on healthy networks — this
works. The bubble appears on the recipient's screen seconds later. The
sender side shows no error icon.

But for the failure modes, all of which surface in WeChat's UI but never in
the AppleScript return code:

- **Recipient has blocked you** → message bubble appears on YOUR side, but
  a separate system row gets inserted below saying「消息已发出，但被对方拒收了」
- **Recipient deleted you** → similar pattern
- **Network failure mid-send** → bubble appears with a red exclamation icon
  and a "retry" button
- **Message blocked by content filter** → red icon, sometimes silent removal
- **File over WeChat's size limit** → modal dialog blocks send entirely;
  no bubble ever appears

In all five cases, the AppleScript that pressed Cmd+V+Enter returned 0.

For a human user this is fine — they're looking at WeChat. They see the icon.
They retry manually.

For an AI agent driving the CLI via JSON envelope, **none of those signals
exist**. The agent reads `{ok: true}` and moves on. If you've got a cron sending
daily reports to your wife, you find out about it weeks later when she asks
why you've gone quiet. (Hypothetically.)

## Why fire-and-forget is wrong for agents (in 100 words)

A human running `git push` and noticing a red error in the terminal is OK —
they'll retry. A human noticing their WeChat message is grayed out is OK —
they'll resend. Humans have a parallel out-of-band signal: their eyes on a
GUI.

Agents have only what your CLI tells them. If your CLI's `ok` boolean is
optimistic — "I pressed Send, therefore success" — your agent will confidently
automate failure at scale. The envelope is the contract; if the contract lies,
the agent has no recovery path.

A CLI that drives a GUI app is acting as a translator between two worlds: the
GUI's optimistic ephemeral UI signals (icons, badges, system rows) and the
agent's strict structured contract. The translator's job is to **wait long
enough to see the bad news** before declaring success.

## Fix attempt 1: poll the AX tree for failure markers (and the second mistake)

The obvious fix: after Cmd+V+Enter, keep polling WeChat's AX tree for ~6
seconds. If any of the last few message rows contain a known failure marker
(`重发`, `被对方拒收`, `retry`, `resend`, `send failed`, etc.) — return
`{ok: false, error: {code: "send_failed_at_recipient"}}`.

```python
# Pseudo-code v1
deadline = time.time() + 6.0
saw_clean = None
while time.time() < deadline:
    rows = get_message_rows()
    if any(find_failure_marker(r) for r in rows[-3:]):
        return {ok: False, ...}
    if saw_clean is None:
        saw_clean = time.time()
    elif time.time() - saw_clean > 1.5:
        return {ok: True, ...}  # 1.5s of clean = verified
    time.sleep(0.35)
return {ok: True, verified: False, reason: "timeout"}
```

Looked right. Wrote tests. Pushed. Tested with my self-chat for sanity:

```bash
$ macli wx send 文件传输助手 "test"
... waited 12 seconds ...
{"ok": false, "error_code": "verify_timeout"}
```

Wait what. My self-chat — the most reliable destination on the planet — was
now failing verification.

Added debug counters. Polls completed in the 6s window: **1**.

A single AX tree traversal on a busy WeChat (hundreds of rows of history)
takes **3-5 seconds** by itself. My "polling at 0.35s intervals" was a
fantasy — one poll consumed almost the entire budget. My "1.5s consecutive
clean" counter logic could never accumulate because there were never two
polls within the same observation.

This is a textbook case of premature optimization without measurement. I'd
designed a fast-polling loop without checking that the underlying operation
was fast enough to support fast polling.

## Fix attempt 2: use the whole timeout as the observation window

The redesign was almost subtraction:

```python
# Pseudo-code v2
deadline = time.time() + 6.0
saw_rows = False
while time.time() < deadline:
    rows = get_message_rows()
    if rows:
        saw_rows = True
        if any(find_failure_marker(r) for r in rows[-3:]):
            return {ok: False, ...}
    time.sleep(0.35)
return {ok: True if saw_rows else False, ...}
```

The shift: instead of tracking "how long has it been clean", just poll until
deadline. If we ever see rows AND never see a marker, declare verified at
deadline. The slow AX traversal IS the observation time — we don't need a
second counter.

This passed both tests:

```bash
$ macli wx send 文件传输助手 "test"        # ✅ verified=true (16s)
$ macli wx send 张量观察tensorscan "test"  # ❌ ok=false, detected="被对方拒收" (10s)
```

## What actually saved me: behavior tests, not unit tests

I'd had unit tests for `_envelope`, `_kb_score`, `_kb_parse_frontmatter` —
all 127 of them — for a while. They never caught any of this. They couldn't.
They were testing the internal data shape of helper functions. The send-doesn't-verify
bug lived in the seam between Python and a GUI app.

What caught it was a different test category, written via [Matt's TDD skill](https://github.com/anthropics/skills):

```python
def test_blocked_contact_returns_send_failed_at_recipient():
    """Sending to a blocked contact must return ok=false with the right code."""
    result = subprocess.run(
        ["./macli", "wx", "send", BLOCKED_USER, "test", "--json"],
        capture_output=True, text=True,
    )
    env = json.loads(result.stdout)
    assert env["ok"] is False
    assert env["error"]["code"] == "send_failed_at_recipient"
```

This test exercises the actual CLI end-to-end. It survives any internal
refactor that doesn't change observable behavior. Three different verify
algorithms ran against the same test — only one made it green.

The TDD skill's core teaching: **test through the public interface**. For a
CLI, the public interface is the binary. For my private `_verify_last_message`
helper to do its job, I needed proof that wrapped around the entire binary,
not around the helper itself.

## Non-retriable failures: don't spam the chat

One more wrinkle. Once verify caught the rejection, my retry logic kicked
in (default `--retry 1`) and sent the message again, generating a SECOND
"被对方拒收" system row in the chat. Six attempts later, the chat history
looked like spam.

Fix: classify "被对方拒收" / "拉黑" / "rejected by" as `NON_RETRIABLE`. When
detected, return immediately, don't burn retry attempts. The user blocked me;
no amount of retrying will unblock them.

```python
NON_RETRIABLE = ("被对方拒收", "已被对方拉黑", "拉黑", "rejected by")
if any(kw in detected for kw in NON_RETRIABLE):
    retry_n = 0  # short-circuit further attempts
```

The general principle: **don't retry failures that aren't transient**. Block
status doesn't change in 800ms. Quota exhaustion doesn't change in 800ms.
Distinguishing transient vs permanent failures is half the work of robust
automation.

## What I shipped (and what I learned)

`macli wx send` now:

- Verifies by default (`--no-verify` to opt out for batch ops)
- Retries transient failures up to N (default 1) via `--retry N`
- Detects permanent failures (block/拒收) and short-circuits retry
- Appends one NDJSON line per call to `~/.tx/wx_send.log` (audit)
- Fires a macOS desktop notification on non-TTY failure (cron-friendly)

Plus an entire self-describing layer: `macli help <cmd> --json` returns the
full contract for any command, `macli help errors --json` returns the error
code inventory, etc. The skill file that points agents at this CLI shrunk
from 302 lines to 85 — because everything specific now lives in the CLI
itself, queryable, never stale.

If you build CLIs that AI agents will drive:

1. **Your `ok` boolean is a contract, not a hope.** Treat it like a function
   signature — its meaning must be precise and verified.
2. **GUI seams need active observation, not optimistic assumption.** Anything
   between you and a GUI app's success state needs polling, not faith.
3. **Behavior tests via subprocess > unit tests of helpers.** The former
   survive refactors and catch contract violations. The latter pin
   implementation details that you'll later want to change.
4. **Distinguish retriable from permanent failure** before adding retry logic.
   Retrying permanent failures is worse than failing fast — it's failing
   loudly and repeatedly.
5. **Let the CLI describe itself** instead of writing a fat skill file.
   The CLI is always fresh; documentation goes stale within a sprint.

Source: [github.com/BuddhaYi/macos-cli](https://github.com/BuddhaYi/macos-cli)
(single-file Python, zero pip deps, MIT, vendored backends, 193 tests green.)

## Postscript: from "one CLI" to "agent skill, anywhere"

Once you have a self-describing CLI, plugging it into a new agent ecosystem
is a `ln -s` away. The same 85-line SKILL.md serves multiple hosts:

```bash
# Host 1 — Claude Code (per-user skills directory)
ln -sf $(pwd)/SKILL.md   ~/.claude/skills/macos-cli/SKILL.md
ln -sf $(pwd)/SCHEMA.md  ~/.claude/skills/macos-cli/SCHEMA.md

# Host 2 — opencode-based projects (per-project skills directory)
ln -sf $(pwd)/SKILL.md   <project>/.opencode/skills/macos-cli/SKILL.md
ln -sf $(pwd)/SCHEMA.md  <project>/.opencode/skills/macos-cli/SCHEMA.md
```

No copying, no translation, no second source of truth. The CLI updates and
both hosts see the new behavior on the next `macli help --json` query —
because that's where the *real* contract lives. The .md files are pointers,
not duplicates.

When integrating into a project with its own safety rules (e.g. a system
where AI must declare itself before messaging users), the skill is scoped
in the project's `AGENTS.md` with a short "binding" block:

```markdown
## External CLI Tools (Scope: subject to §1-§4 above)

This project integrates macos-cli via .opencode/skills/macos-cli/. Scope:
- macli wx send: subject to §3 — declare AI identity in first chat turn
- macli x post/like/reply: disabled by default; require explicit user intent
- macli mac script: subject to §2 — no financial / app-removal / data-wipe
- macli does NOT replace trigger_emergency (§4) — emergencies stay on MCP
```

This isn't fan-fiction documentation — it's an actual binding the model
respects, because it reads the project's AGENTS.md before invoking any
external tool. The same CLI gets different *latitude* in different hosts,
governed by host-local rules, with no CLI changes.

The X thread version of this story:
[x.com/YiT_Buddha/status/2054400908172337429](https://x.com/YiT_Buddha/status/2054400908172337429)
(7-tweet thread, ~3 screenshots, same arc).

---

*Built with macOS, AppleScript, pyobjc, and the patience to ship a `ok:true`
bug before catching it. Thanks to [Matt's TDD skill](https://github.com/anthropics/skills)
for teaching test-via-public-interface — it's the difference between knowing
your code works and knowing your CLI works.*
