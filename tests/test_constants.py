"""Tests for module-level constants in macli.

These guard against accidental schema-version bumps, missing notification
title mappings, and version-string drift.
"""

import re


class TestVersionConstants:
    def test_schema_version_is_string_one(self, macli):
        # SCHEMA.md pins schema_version: "1" — must be a string, not int
        assert macli.SCHEMA_VERSION == "1"
        assert isinstance(macli.SCHEMA_VERSION, str)

    def test_version_shape(self, macli):
        # MAJOR.MINOR.PATCH (semver-ish)
        assert re.match(r"^\d+\.\d+\.\d+$", macli.VERSION), \
            f"VERSION {macli.VERSION!r} does not look like semver"

    def test_version_not_empty(self, macli):
        assert macli.VERSION
        assert isinstance(macli.VERSION, str)


class TestWxFailTitles:
    """Notification titles for failed wx send. Each known error code must
    have a distinct, non-empty Chinese-prefixed title."""

    EXPECTED_KEYS = {
        "send_failed_at_recipient",
        "verify_timeout",
        "send_failed",
        "not_found",
        "verify_error",
        "internal_error",
    }

    def test_all_expected_codes_present(self, macli):
        keys = set(macli._WX_FAIL_TITLES.keys())
        missing = self.EXPECTED_KEYS - keys
        assert not missing, f"missing notification titles for: {missing}"

    def test_titles_are_non_empty_strings(self, macli):
        for code, title in macli._WX_FAIL_TITLES.items():
            assert isinstance(title, str), f"{code} title is not a string"
            assert title, f"{code} has empty title"

    def test_titles_all_prefixed_with_macli_wx(self, macli):
        # The convention is "macli wx: <reason>" — guards typos like
        # "mac wx" or "macli  wx"
        for code, title in macli._WX_FAIL_TITLES.items():
            assert title.startswith("macli wx: "), \
                f"{code} title {title!r} missing 'macli wx: ' prefix"

    def test_distinct_titles_per_code(self, macli):
        # Distinct titles enable triage at a glance — duplicates defeat that
        titles = list(macli._WX_FAIL_TITLES.values())
        assert len(titles) == len(set(titles)), \
            "duplicate notification titles defeat at-a-glance triage"


class TestXInternalSet:
    def test_known_internal_commands_present(self, macli):
        # These are routed to the X subsystem rather than passthrough
        for cmd in ("auth", "archive", "cookies-save", "doctor",
                    "download", "help"):
            assert cmd in macli.X_INTERNAL, f"{cmd} should be X-internal"


class TestPaths:
    def test_root_is_repo_dir(self, macli):
        # ROOT should resolve to the directory containing macli
        assert macli.ROOT.is_dir()
        assert (macli.ROOT / "macli").exists()

    def test_cache_dir_under_home(self, macli):
        # All X subsystem state lives in ~/.tx (so old magpie users carry over)
        assert macli.CACHE_DIR.name == ".tx"
        assert str(macli.CACHE_DIR).startswith(str(macli.Path.home()))

    def test_cache_ttl_is_one_week(self, macli):
        assert macli.CACHE_TTL == 7 * 24 * 3600
