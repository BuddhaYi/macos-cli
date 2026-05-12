"""Tests for _is_auth_error — twitter-cli/bird stderr classifier.

Implementation lowercases the stderr text and looks for any of:
    "401", "could not authenticate", "missing required credentials",
    "no twitter cookies", "missing auth_token", "missing ct0"
"""

import pytest


class TestIsAuthErrorPositiveMatches:
    @pytest.mark.parametrize("stderr_text,desc", [
        ("HTTP 401 Unauthorized", "bare 401"),
        ("got 401 back from twitter", "401 lowercase context"),
        ("Could not authenticate you", "title-case authenticate"),
        ("could not authenticate you", "lowercase authenticate"),
        ("COULD NOT AUTHENTICATE you", "uppercase authenticate"),
        ("Error: missing required credentials", "missing creds full"),
        ("No twitter cookies found in env", "no twitter cookies"),
        ("Missing AUTH_TOKEN", "missing auth_token uppercase"),
        ("missing auth_token", "missing auth_token lowercase"),
        ("Missing CT0", "missing ct0 uppercase"),
        ("missing ct0", "missing ct0 lowercase"),
    ])
    def test_matches_known_auth_phrase(self, macli, stderr_text, desc):
        assert macli._is_auth_error(stderr_text) is True, \
            f"expected True for: {desc}  ({stderr_text!r})"


class TestIsAuthErrorNegative:
    @pytest.mark.parametrize("stderr_text", [
        "",  # empty
        "404 not found",  # unrelated HTTP code
        "500 internal server error",
        "timeout while fetching",
        "ECONNREFUSED",
        "rate limited; please retry",
        "no such file or directory",
        "command not found: twitter",
    ])
    def test_unrelated_errors_not_auth(self, macli, stderr_text):
        assert macli._is_auth_error(stderr_text) is False, \
            f"unexpected auth-match for: {stderr_text!r}"

    def test_none_input(self, macli):
        assert macli._is_auth_error(None) is False

    def test_empty_string(self, macli):
        assert macli._is_auth_error("") is False


class TestIsAuthErrorEdgeCases:
    def test_substring_in_larger_message(self, macli):
        # 401 embedded in noise (e.g. log prefix)
        assert macli._is_auth_error("[debug 2024-01-01] req=abc resp 401 ...") is True

    def test_multiline_stderr(self, macli):
        msg = (
            "stack trace:\n"
            "  at foo\n"
            "Caused by: Missing CT0 token in env\n"
        )
        assert macli._is_auth_error(msg) is True

    def test_unicode_stderr_with_auth(self, macli):
        # 中文 mixed with our trigger phrase still classifies as auth
        assert macli._is_auth_error("登录失败: 401 unauthorized") is True

    def test_unicode_stderr_without_auth(self, macli):
        assert macli._is_auth_error("网络错误: 超时") is False

    def test_4010_does_match(self, macli):
        # KNOWN behavior: "401" is matched by substring, so "4010" or
        # "/api/4010" would trigger. We assert this so future refactors
        # are intentional about the trade-off.
        assert macli._is_auth_error("error 4010 something") is True

    def test_case_insensitive_full_message(self, macli):
        assert macli._is_auth_error("MISSING AUTH_TOKEN IN ENVIRONMENT") is True
