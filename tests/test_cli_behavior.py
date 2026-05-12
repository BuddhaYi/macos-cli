"""Integration tests for macli's public CLI surface.

Per the TDD skill (~/.claude/skills/tdd/SKILL.md): tests live at the public
interface so they survive internal refactors. Each test invokes the `./macli`
binary via subprocess and asserts on observable outputs (exit code, stdout
JSON envelope, stderr text). Internal helper functions are NOT touched here —
those live in test_envelope/test_auth/test_kb_search/test_constants, which
pin implementation detail but break on rename.
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MACLI_BIN = ROOT / "macli"


def run_macli(*args, timeout=15):
    """Run `./macli args...` and return the CompletedProcess."""
    return subprocess.run(
        [str(MACLI_BIN), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def run_json(*args, timeout=15):
    """Run `./macli ... --json`; return (returncode, parsed_envelope_dict)."""
    proc = run_macli(*args, "--json", timeout=timeout)
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(
            f"stdout was not valid JSON.\n"
            f"  args: {args}\n"
            f"  rc:   {proc.returncode}\n"
            f"  stdout (first 400): {proc.stdout[:400]!r}\n"
            f"  stderr (first 400): {proc.stderr[:400]!r}\n"
            f"  jsonerror: {e}"
        )
    return proc.returncode, envelope


# ─── T1: TRACER BULLET — doctor envelope shape ──────────────────────────────
# Proves: subprocess harness works, JSON parse works, vendor map is stable.

def test_doctor_returns_envelope_with_five_vendors():
    rc, env = run_json("doctor")
    assert rc == 0
    assert env["ok"] is True
    assert env["schema_version"] == "1"

    vendors = env["data"]["vendors"]
    assert set(vendors.keys()) == {
        "bird", "twitter-cli", "opencli", "macos-automator-mcp", "wechat-mcp"
    }
    # kb_count is observable in two places — top-level and inside the
    # automator vendor entry — both should agree.
    assert env["data"]["kb_count"] == vendors["macos-automator-mcp"]["kb_count"]


# ─── T2: stats has four headline sections ───────────────────────────────────
# Gap filler: macli stats was added in v0.4 with zero existing coverage.

def test_stats_returns_four_sections():
    rc, env = run_json("stats")
    assert rc == 0
    assert env["ok"] is True

    data = env["data"]
    for required in ("bookmarks", "cookies", "kb", "archive_log"):
        assert required in data, f"stats --json missing section: {required}"

    # bookmarks section has the contract we document
    assert "total" in data["bookmarks"]
    assert isinstance(data["bookmarks"]["total"], int)


# ─── T3: kb-search RANKS pdf-relevant scripts above unrelated ───────────────
# This is the behavior end-users actually care about — not "count > 0".

def test_kb_search_ranks_topical_scripts_first():
    rc, env = run_json("mac", "kb-search", "save webpage as PDF", "--max", "5")
    assert rc == 0
    assert env["ok"] is True

    results = env["data"]["results"]
    assert len(results) >= 1, "expected at least one match for 'save webpage as PDF'"

    # Top hit must be topical: id mentions pdf or safari or webpage
    top = results[0]
    blob = (top["id"] + " " + (top.get("title") or "")).lower()
    assert any(t in blob for t in ("pdf", "safari", "webpage", "save")), (
        f"top result is not topical: id={top['id']!r}, title={top.get('title')!r}"
    )

    # Scores are monotonically non-increasing
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), (
        f"results not sorted by score desc: {scores}"
    )


# ─── T4: doctor --fix --json has structured repairs[] ───────────────────────

def test_doctor_fix_returns_repairs_section():
    rc, env = run_json("doctor", "--fix", timeout=60)
    assert rc == 0
    assert env["ok"] is True

    data = env["data"]
    assert "repairs" in data, "doctor --fix missing repairs[]"
    assert "repairs_applied" in data
    assert isinstance(data["repairs"], list)
    assert isinstance(data["repairs_applied"], int)
    assert data["repairs_applied"] == len(data["repairs"])


# ─── T5: kb-list ordering is alphabetical & stable ──────────────────────────
# This is a documented but untested invariant: callers can rely on stable
# ordering for diffing across vendor upgrades.

def test_kb_list_is_alphabetically_sorted():
    rc, env = run_json("mac", "kb-list")
    assert rc == 0
    assert env["ok"] is True

    scripts = env["data"]["scripts"]
    ids = [s["id"] for s in scripts]
    assert ids == sorted(ids), (
        f"kb-list IDs not alphabetical (first 5: {ids[:5]})"
    )
    assert env["data"]["count"] == len(scripts)


# ─── T6: invalid-args envelope is invariant across commands ─────────────────
# The contract advertised by SCHEMA.md: missing positional args always yield
# ok:false + error.code=invalid_args. If a command silently 0-exits or
# returns a different code, agents can't reliably react.

@pytest.mark.parametrize("argv", [
    ("wx", "send"),
    ("wx", "read"),
    ("mac", "kb"),
    ("mac", "kb-search"),
    ("mac", "script"),
])
def test_invalid_args_envelope_is_uniform(argv):
    rc, env = run_json(*argv)
    assert rc != 0, f"{argv} should exit non-zero on missing args"
    assert env["ok"] is False
    assert env["error"]["code"] == "invalid_args", (
        f"{argv} returned error.code={env['error']['code']!r}, "
        f"expected 'invalid_args'"
    )


# ─── T7: every internal --json command produces parseable JSON ──────────────
# Per SCHEMA.md, internal commands implement the envelope themselves; X
# subsystem passes through to upstream JSON. This test catches a class of
# bug where a new code path forgets to JSON-encode (e.g. trailing log noise
# mixed into stdout).

@pytest.mark.parametrize("argv", [
    ("doctor",),
    ("stats",),
    ("mac", "volume"),
    ("mac", "kb-list"),
    ("mac", "kb-search", "system"),
    ("x", "cookies-save", "--check-age"),
])
def test_internal_command_json_is_parseable(argv):
    rc, env = run_json(*argv)
    # We don't care about ok=True vs False here — only that stdout is JSON
    # and shape conforms to the envelope.
    assert "ok" in env
    assert env["schema_version"] == "1"
    assert isinstance(env["ok"], bool)
    if env["ok"]:
        assert "error" not in env or env.get("error") is None
    else:
        assert "error" in env
        assert "code" in env["error"]
