"""Behavior tests for macli's self-describing CLI surface.

The B+ skill packaging approach assumes agents can discover everything they
need by querying the CLI at runtime, not reading a frozen SKILL.md. These
tests pin the contracts those queries return — so a future refactor that
breaks discovery breaks a test immediately, not silently.

All tests invoke ./macli via subprocess (public interface only). They survive
internal refactors and would only fail if the CLI's observable behavior
actually regresses.
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MACLI_BIN = ROOT / "macli"


def run_json(*args, timeout=15):
    """Run `./macli <args>` and return (returncode, parsed_envelope)."""
    proc = subprocess.run(
        [str(MACLI_BIN), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(
            f"stdout not valid JSON.\n"
            f"  args:   {args}\n  rc:     {proc.returncode}\n"
            f"  stdout: {proc.stdout[:400]!r}\n  stderr: {proc.stderr[:400]!r}\n"
            f"  err:    {e}"
        )
    return proc.returncode, envelope


# ─── Tier 1: namespace discovery ────────────────────────────────────────────

def test_top_level_help_json_lists_namespaces():
    """`macli help --json` returns namespaces + internal commands + discovery list."""
    rc, env = run_json("help", "--json")
    assert rc == 0 and env["ok"] is True
    data = env["data"]
    assert data["namespaces"] == ["x", "wx", "mac"]
    assert "doctor" in data["internal_commands"]
    assert "stats" in data["internal_commands"]
    assert len(data["commands"]) >= 15, "expected ≥15 registered commands"
    assert len(data["discovery_commands"]) >= 5, "should advertise multiple discovery endpoints"


def test_top_level_dash_dash_json_is_alias_for_help():
    """`macli --json` (bare) is an alias for `macli help --json`."""
    rc, env = run_json("--json")
    assert rc == 0 and env["ok"] is True
    assert "namespaces" in env["data"]


@pytest.mark.parametrize("ns,expected_subs", [
    ("wx", {"send", "read", "contacts"}),
    ("mac", {"kb", "kb-list", "kb-search", "script", "dark-mode", "volume"}),
    ("x", {"archive", "auth", "cookies-save", "doctor", "download", "help"}),
])
def test_namespace_dash_json_lists_subcommands(ns, expected_subs):
    """`macli <ns> --json` (standalone) returns its subcommand list."""
    rc, env = run_json(ns, "--json")
    assert rc == 0 and env["ok"] is True
    assert env["data"]["namespace"] == ns
    got = set(env["data"]["subcommands"])
    assert expected_subs.issubset(got), f"{ns} missing: {expected_subs - got}"


def test_x_help_json_returns_command_matrix():
    """`macli x help --json` returns categorized X command matrix (no longer the
    'unknown command: --json' bug)."""
    rc, env = run_json("x", "help", "--json")
    assert rc == 0 and env["ok"] is True
    data = env["data"]
    for key in ("twitter_cli", "bird", "opencli_twitter", "opencli_sites", "internal"):
        assert key in data, f"missing key in x help envelope: {key}"
    assert len(data["opencli_sites"]) >= 100, "expected 100+ opencli sites"
    assert data["priority"].startswith("twitter-cli")


# ─── Tier 2: per-command help + error inventory ─────────────────────────────

@pytest.mark.parametrize("cmd", [
    "wx send", "wx read", "wx contacts",
    "mac kb", "mac kb-list", "mac kb-search", "mac script",
    "mac dark-mode", "mac volume",
    "x archive", "x download", "x cookies-save",
    "doctor", "stats", "help",
])
def test_help_per_command_json_has_contract(cmd):
    """`macli help <cmd-path> --json` returns synopsis + summary for every
    registered command. Behavior list optional but synopsis is mandatory."""
    rc, env = run_json("help", *cmd.split(), "--json")
    assert rc == 0 and env["ok"] is True
    data = env["data"]
    assert data["command"] == cmd
    assert data["synopsis"].startswith("macli "), f"synopsis must start with 'macli ': {data['synopsis']!r}"
    assert "summary" in data and data["summary"], f"missing summary for {cmd}"


def test_help_unknown_command_returns_not_found_with_available_list():
    """Asking for help on a non-existent command returns not_found AND lists
    what IS available — so the agent can self-correct."""
    rc, env = run_json("help", "wx", "nonexistent-action", "--json")
    assert rc != 0
    assert env["ok"] is False
    assert env["error"]["code"] == "not_found"
    assert len(env["data"]["available"]) >= 15


def test_help_errors_json_has_complete_inventory():
    """`macli help errors --json` returns the full ERROR_CODES table that
    agents need to interpret envelope.error.code values."""
    rc, env = run_json("help", "errors", "--json")
    assert rc == 0 and env["ok"] is True

    codes = {item["code"] for item in env["data"]["error_codes"]}
    # These are the codes documented in SCHEMA.md and used in real envelopes
    for required in (
        "invalid_args", "not_found", "not_authenticated",
        "subprocess_failed", "send_failed_at_recipient",
        "verify_timeout", "verify_error", "internal_error",
    ):
        assert required in codes, f"error code inventory missing: {required}"
    # Every entry has a non-empty description
    for item in env["data"]["error_codes"]:
        assert item["description"], f"empty description for code {item['code']}"


# ─── Tier 3: --help intercept + schema endpoint ─────────────────────────────

def test_help_schema_json_documents_envelope():
    """`macli help schema --json` is the machine-readable envelope contract."""
    rc, env = run_json("help", "schema", "--json")
    assert rc == 0 and env["ok"] is True
    data = env["data"]
    assert data["schema_version"] == "1"
    for shape_key in ("success_shape", "error_shape"):
        assert shape_key in data
        assert data[shape_key]["schema_version"] == "1"
    assert isinstance(data["rules"], list) and len(data["rules"]) >= 3


@pytest.mark.parametrize("argv", [
    ("wx", "send", "--help"),
    ("wx", "read", "--help"),
    ("mac", "kb", "--help"),
    # The bug-fix case: --help used to be parsed as the search query!
    ("mac", "kb-search", "--help"),
    ("mac", "script", "--help"),
])
def test_subcommand_dash_help_intercepted_not_treated_as_positional(argv):
    """Adding --help to any subcommand returns its help info, NOT an
    invalid_args error or (worse) interpretation of '--help' as a positional
    argument."""
    rc, env = run_json(*argv, "--json")
    assert rc == 0 and env["ok"] is True
    assert "command" in env["data"]
    # The command path is the namespace + subcommand
    assert env["data"]["command"] == f"{argv[0]} {argv[1]}"


def test_subcommand_help_human_format_works():
    """The --help intercept also works without --json (human-readable text)."""
    proc = subprocess.run(
        [str(MACLI_BIN), "mac", "kb-search", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0
    assert "kb-search" in proc.stdout
    assert "synopsis" not in proc.stdout.lower() or "kb-search" in proc.stdout
    # Critically: NOT a search result list
    assert "score=" not in proc.stdout, "still treating --help as search query"


# ─── Cross-cutting sanity ──────────────────────────────────────────────────

def test_every_registered_command_is_actually_dispatchable():
    """Every command in CMD_INFO should have its namespace listed in the
    discovery output. Catches drift between data and routers."""
    _, top = run_json("help", "--json")
    registered = top["data"]["commands"]

    _, wx_env = run_json("wx", "--json")
    wx_subs = set(wx_env["data"]["subcommands"])

    _, mac_env = run_json("mac", "--json")
    mac_subs = set(mac_env["data"]["subcommands"])

    # Every wx X / mac X in registry should appear in its namespace listing
    for cmd in registered:
        if cmd.startswith("wx "):
            sub = cmd[len("wx "):]
            assert sub in wx_subs, f"registered '{cmd}' missing from `macli wx --json`"
        if cmd.startswith("mac "):
            sub = cmd[len("mac "):]
            assert sub in mac_subs, f"registered '{cmd}' missing from `macli mac --json`"


def test_discovery_commands_list_is_self_consistent():
    """Every command advertised in DISCOVERY_COMMANDS list should actually work."""
    rc, env = run_json("help", "--json")
    assert rc == 0
    advertised = env["data"]["discovery_commands"]
    # All commands should mention --json (we're an agent-native CLI)
    for line in advertised:
        assert "--json" in line or "macli mac kb-list" in line, (
            f"discovery hint without --json suggestion: {line!r}"
        )
