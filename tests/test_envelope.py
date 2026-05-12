"""Tests for envelope/flag/int-parser helpers in macli.

Covers:
  - _envelope(ok, data, error_code, error_message)
  - _has_flag(args, *flags)
  - _parse_int_flag(args, flag, default)
"""

import json


# ---------------------------------------------------------------------------
# _envelope
# ---------------------------------------------------------------------------

class TestEnvelopeSuccess:
    def test_minimal_success(self, macli):
        env = macli._envelope(True)
        assert env == {"ok": True, "schema_version": "1"}

    def test_success_with_data_dict(self, macli):
        env = macli._envelope(True, data={"count": 3})
        assert env["ok"] is True
        assert env["data"] == {"count": 3}
        assert env["schema_version"] == "1"
        assert "error" not in env

    def test_success_with_data_list(self, macli):
        env = macli._envelope(True, data=[1, 2, 3])
        assert env["data"] == [1, 2, 3]

    def test_success_with_data_empty_dict(self, macli):
        # empty dict is *not* None — should still appear
        env = macli._envelope(True, data={})
        assert "data" in env
        assert env["data"] == {}

    def test_success_with_data_empty_list(self, macli):
        env = macli._envelope(True, data=[])
        assert "data" in env
        assert env["data"] == []

    def test_success_with_data_zero(self, macli):
        # 0 is falsy but not None — should still appear
        env = macli._envelope(True, data=0)
        assert "data" in env
        assert env["data"] == 0

    def test_success_with_data_false(self, macli):
        # False is falsy but not None — should still appear
        env = macli._envelope(True, data=False)
        assert "data" in env
        assert env["data"] is False

    def test_success_with_none_data_omits_key(self, macli):
        env = macli._envelope(True, data=None)
        assert "data" not in env

    def test_success_truthy_non_bool_is_coerced(self, macli):
        # 1 → True, "yes" → True (we use bool(ok))
        assert macli._envelope(1)["ok"] is True
        assert macli._envelope("yes")["ok"] is True

    def test_success_unicode_payload_round_trips(self, macli):
        env = macli._envelope(True, data={"msg": "你好 — émoji 🎉"})
        # Must survive json.dumps without errors
        s = json.dumps(env, ensure_ascii=False)
        assert "你好" in s
        assert "🎉" in s


class TestEnvelopeError:
    def test_error_minimal_defaults(self, macli):
        env = macli._envelope(False)
        assert env["ok"] is False
        assert env["error"] == {"code": "internal_error", "message": ""}
        assert env["schema_version"] == "1"

    def test_error_with_code_and_message(self, macli):
        env = macli._envelope(False, error_code="not_found",
                              error_message="contact not found")
        assert env["error"]["code"] == "not_found"
        assert env["error"]["message"] == "contact not found"

    def test_error_with_only_code(self, macli):
        env = macli._envelope(False, error_code="timeout")
        assert env["error"] == {"code": "timeout", "message": ""}

    def test_error_with_only_message(self, macli):
        env = macli._envelope(False, error_message="boom")
        # Missing code falls back to "internal_error"
        assert env["error"] == {"code": "internal_error", "message": "boom"}

    def test_error_with_data_payload(self, macli):
        # Caller may include diagnostic data even on error
        env = macli._envelope(False, data={"attempts": 3},
                              error_code="send_failed")
        assert env["data"] == {"attempts": 3}
        assert env["error"]["code"] == "send_failed"

    def test_error_falsy_coerced(self, macli):
        # 0 → False, "" → False
        assert macli._envelope(0)["ok"] is False
        assert macli._envelope("")["ok"] is False

    def test_error_message_unicode(self, macli):
        env = macli._envelope(False, error_code="invalid_args",
                              error_message="参数错误：缺少必需字段")
        assert env["error"]["message"] == "参数错误：缺少必需字段"


class TestEnvelopeJsonRoundTrip:
    def test_dumps_and_loads(self, macli):
        env = macli._envelope(True, data={"a": 1, "b": [1, 2]})
        s = json.dumps(env)
        assert json.loads(s) == env

    def test_includes_schema_version_always(self, macli):
        # The schema requires every envelope to carry schema_version
        assert "schema_version" in macli._envelope(True)
        assert "schema_version" in macli._envelope(False)
        assert "schema_version" in macli._envelope(True, data={"x": 1})
        assert "schema_version" in macli._envelope(False, error_code="x")


# ---------------------------------------------------------------------------
# _has_flag
# ---------------------------------------------------------------------------

class TestHasFlag:
    def test_present_single_flag(self, macli):
        assert macli._has_flag(["--json"], "--json") is True

    def test_present_one_of_several(self, macli):
        assert macli._has_flag(["--quiet", "--json"], "--json", "--verbose") is True

    def test_absent(self, macli):
        assert macli._has_flag(["foo", "bar"], "--json") is False

    def test_empty_args(self, macli):
        assert macli._has_flag([], "--json") is False

    def test_no_flags_passed_returns_false(self, macli):
        # any([]) is False — no flags to look for means no match
        assert macli._has_flag(["--json"]) is False

    def test_exact_match_only_no_substring(self, macli):
        # "--js" is not "--json", "--jsonx" is not "--json"
        assert macli._has_flag(["--js", "--jsonx"], "--json") is False

    def test_works_for_non_flag_tokens(self, macli):
        # Function is purely "is X in list" — no actual flag semantics
        assert macli._has_flag(["hello"], "hello") is True

    def test_case_sensitive(self, macli):
        assert macli._has_flag(["--JSON"], "--json") is False

    def test_multiple_aliases_matches_any(self, macli):
        assert macli._has_flag(["-v"], "--verbose", "-v") is True
        assert macli._has_flag(["--verbose"], "--verbose", "-v") is True
        assert macli._has_flag(["foo"], "--verbose", "-v") is False


# ---------------------------------------------------------------------------
# _parse_int_flag
# ---------------------------------------------------------------------------

class TestParseIntFlag:
    def test_present_with_int_value(self, macli):
        val, rest = macli._parse_int_flag(["--max", "20"], "--max", 10)
        assert val == 20
        assert rest == []

    def test_present_with_int_value_strips_flag_and_value(self, macli):
        val, rest = macli._parse_int_flag(
            ["a", "--max", "5", "b"], "--max", 10
        )
        assert val == 5
        assert rest == ["a", "b"]

    def test_absent_returns_default(self, macli):
        val, rest = macli._parse_int_flag(["a", "b"], "--max", 10)
        assert val == 10
        assert rest == ["a", "b"]

    def test_absent_does_not_mutate_args(self, macli):
        original = ["a", "b"]
        _, rest = macli._parse_int_flag(original, "--max", 10)
        assert original == ["a", "b"]
        # When absent the function returns the same args reference, which is
        # fine because callers downstream rebind. Ensure shape matches.
        assert rest == original

    def test_present_does_not_mutate_input(self, macli):
        original = ["--max", "5", "trailing"]
        val, rest = macli._parse_int_flag(original, "--max", 10)
        assert original == ["--max", "5", "trailing"], \
            "input list must not be mutated (immutability rule)"
        assert val == 5
        assert rest == ["trailing"]

    def test_flag_at_end_with_no_value_returns_default(self, macli):
        val, rest = macli._parse_int_flag(["x", "--max"], "--max", 7)
        assert val == 7
        # No mutation; rest should be the original args
        assert rest == ["x", "--max"]

    def test_non_int_value_returns_default(self, macli):
        val, rest = macli._parse_int_flag(["--max", "abc"], "--max", 9)
        assert val == 9
        # Implementation returns original args on non-int parse failure
        assert rest == ["--max", "abc"]

    def test_negative_int_parsed(self, macli):
        val, rest = macli._parse_int_flag(["--retry", "-1"], "--retry", 0)
        assert val == -1
        assert rest == []

    def test_zero_value(self, macli):
        val, rest = macli._parse_int_flag(["--max", "0"], "--max", 10)
        assert val == 0
        assert rest == []

    def test_first_occurrence_only(self, macli):
        # If --max appears twice, only the first one is consumed
        val, rest = macli._parse_int_flag(
            ["--max", "3", "--max", "5"], "--max", 10
        )
        assert val == 3
        assert rest == ["--max", "5"]

    def test_default_returned_when_value_is_float_string(self, macli):
        # int("3.5") raises ValueError → default
        val, rest = macli._parse_int_flag(["--max", "3.5"], "--max", 10)
        assert val == 10
