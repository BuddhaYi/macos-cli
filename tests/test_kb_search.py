"""Tests for the macos-automator-mcp knowledge-base search helpers.

Covers:
  - _kb_parse_frontmatter (stdlib YAML subset)
  - _kb_tokenize
  - _kb_score (weighted token-overlap)
  - _kb_newest_mtime
  - _kb_build_search_index + _kb_load_search_index (end-to-end with tmp_path)
"""

import json
import os
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# _kb_parse_frontmatter
# ---------------------------------------------------------------------------

SIMPLE_FM = """---
id: hello_world
title: Hello World
category: 01_basics
description: A simple hello-world script.
keywords:
  - hello
  - world
---

# body
"""

FOLDED_FM = """---
title: JXA UI Automation
category: 03_jxa_core
id: jxa_ui_automation
description: >-
  Overview of UI automation capabilities for interacting with macOS applications
  using JavaScript for Automation (JXA).
language: javascript
keywords:
  - jxa
  - javascript
  - automation
---

body text
"""

QUOTED_FM = """---
id: "quoted_id"
title: "Quoted Title"
category: "cat_a"
description: "Quoted description line"
keywords:
  - "quoted_kw"
  - plain_kw
---
"""

NO_FRONTMATTER = "# Just a heading\n\nNo frontmatter here.\n"

UNCLOSED_FM = """---
id: oops
title: still going
"""


class TestParseFrontmatter:
    def test_simple_scalars(self, macli):
        fm = macli._kb_parse_frontmatter(SIMPLE_FM)
        assert fm is not None
        assert fm["id"] == "hello_world"
        assert fm["title"] == "Hello World"
        assert fm["category"] == "01_basics"
        assert fm["description"] == "A simple hello-world script."

    def test_simple_keywords_list(self, macli):
        fm = macli._kb_parse_frontmatter(SIMPLE_FM)
        assert fm["keywords"] == ["hello", "world"]

    def test_folded_description_collapses_to_single_line(self, macli):
        fm = macli._kb_parse_frontmatter(FOLDED_FM)
        assert fm["id"] == "jxa_ui_automation"
        assert fm["title"] == "JXA UI Automation"
        # `language: javascript` is mapped onto category-fallback BUT
        # actual category should take precedence
        assert fm["category"] == "03_jxa_core"
        assert "Overview of UI automation capabilities" in fm["description"]
        # Folded text becomes one line — no embedded newlines
        assert "\n" not in fm["description"]
        assert fm["keywords"] == ["jxa", "javascript", "automation"]

    def test_quoted_scalars_strip_quotes(self, macli):
        fm = macli._kb_parse_frontmatter(QUOTED_FM)
        assert fm["id"] == "quoted_id"
        assert fm["title"] == "Quoted Title"
        assert fm["category"] == "cat_a"
        assert fm["description"] == "Quoted description line"
        assert fm["keywords"] == ["quoted_kw", "plain_kw"]

    def test_no_frontmatter_returns_none(self, macli):
        assert macli._kb_parse_frontmatter(NO_FRONTMATTER) is None

    def test_unclosed_frontmatter_returns_none(self, macli):
        assert macli._kb_parse_frontmatter(UNCLOSED_FM) is None

    def test_empty_string(self, macli):
        assert macli._kb_parse_frontmatter("") is None

    def test_empty_frontmatter_block_returns_dict_with_blanks(self, macli):
        fm = macli._kb_parse_frontmatter("---\n\n---\n")
        # Implementation: re.match(r"^---\n(.*?)\n---", DOTALL) matches the
        # empty block. We expect a populated dict with default blanks.
        assert fm is not None
        assert fm["id"] == ""
        assert fm["title"] == ""
        assert fm["keywords"] == []

    def test_keywords_with_quotes_stripped(self, macli):
        fm = macli._kb_parse_frontmatter(QUOTED_FM)
        # Both quoted and unquoted entries appear bare
        assert "quoted_kw" in fm["keywords"]
        assert "plain_kw" in fm["keywords"]

    def test_language_used_when_category_missing(self, macli):
        # The implementation iterates (id, title, category, language) and
        # stores `language` under category — used only when category is absent.
        text = (
            "---\n"
            "id: lang_only\n"
            "title: Lang Only\n"
            "language: applescript\n"
            "---\n"
        )
        fm = macli._kb_parse_frontmatter(text)
        assert fm["category"] == "applescript"

    def test_unicode_in_values(self, macli):
        text = (
            "---\n"
            "id: 中文_id\n"
            "title: 你好 World\n"
            "category: 国际化\n"
            "description: 测试描述\n"
            "keywords:\n"
            "  - 中文\n"
            "  - english\n"
            "---\n"
        )
        fm = macli._kb_parse_frontmatter(text)
        assert fm["id"] == "中文_id"
        assert fm["title"] == "你好 World"
        assert fm["category"] == "国际化"
        assert fm["description"] == "测试描述"
        assert "中文" in fm["keywords"]


# ---------------------------------------------------------------------------
# _kb_tokenize
# ---------------------------------------------------------------------------

class TestKbTokenize:
    def test_basic_split(self, macli):
        assert macli._kb_tokenize("Hello World") == ["hello", "world"]

    def test_lowercases(self, macli):
        assert macli._kb_tokenize("AbCdEf") == ["abcdef"]

    def test_drops_short_tokens(self, macli):
        # Tokens with len<2 are dropped → "a", "b" lost; "ab" kept
        assert macli._kb_tokenize("a ab b cd") == ["ab", "cd"]

    def test_splits_on_punctuation(self, macli):
        assert macli._kb_tokenize("foo-bar.baz/qux") == ["foo", "bar", "baz", "qux"]

    def test_underscore_kept_as_word_char(self, macli):
        # \w includes underscore so foo_bar stays as one token
        assert macli._kb_tokenize("foo_bar") == ["foo_bar"]

    def test_empty_string(self, macli):
        assert macli._kb_tokenize("") == []

    def test_none_input(self, macli):
        # The function guards against None via `(s or "")`
        assert macli._kb_tokenize(None) == []

    def test_only_punctuation(self, macli):
        assert macli._kb_tokenize("---///") == []

    def test_unicode_word_chars_kept(self, macli):
        # \w matches unicode word chars by default in Python 3
        assert macli._kb_tokenize("你好 world") == ["你好", "world"]

    def test_numeric_tokens(self, macli):
        # Digits are \w so they survive (if len>=2)
        assert macli._kb_tokenize("v0.4.0 build 42") == ["v0", "build", "42"]


# ---------------------------------------------------------------------------
# _kb_score
# ---------------------------------------------------------------------------

class TestKbScore:
    def _entry(self, **kw):
        base = {"title": "", "description": "", "keywords": [],
                "id": "", "category": ""}
        base.update(kw)
        return base

    def test_title_match_weight_3(self, macli):
        e = self._entry(title="Safari Tabs")
        assert macli._kb_score(e, ["safari"]) == 3.0

    def test_keyword_match_weight_2_5(self, macli):
        e = self._entry(keywords=["safari", "tabs"])
        assert macli._kb_score(e, ["safari"]) == 2.5

    def test_id_match_weight_1_5(self, macli):
        # NOTE: id "safari-open-tabs" tokenizes to ["safari","open","tabs"];
        # "safari_open_tabs" is one token (underscore is a word char) and
        # would NOT match query "safari". This is intentional — the KB id
        # convention happens to use underscores, so id-token matches are
        # rare in practice. Documented here so a refactor is intentional.
        e = self._entry(id="safari-open-tabs")
        assert macli._kb_score(e, ["safari"]) == 1.5

    def test_id_with_underscore_is_single_token(self, macli):
        # Underscores keep the id as one token — query "safari" misses it.
        e = self._entry(id="safari_open_tabs")
        assert macli._kb_score(e, ["safari"]) == 0.0
        # But querying the full underscored form DOES hit
        assert macli._kb_score(e, ["safari_open_tabs"]) == 1.5

    def test_description_match_weight_1_0(self, macli):
        e = self._entry(description="Open all safari tabs")
        assert macli._kb_score(e, ["safari"]) == 1.0

    def test_category_match_weight_0_5(self, macli):
        # Same tokenization caveat as id — use a delimiter that splits.
        e = self._entry(category="safari-apps")
        assert macli._kb_score(e, ["safari"]) == 0.5

    def test_multiple_fields_sum(self, macli):
        # token "safari" present in title (3) + keywords (2.5) + id (1.5)
        # + description (1.0) + category (0.5) = 8.5. Note: id and
        # category use hyphens so they tokenize into separate words.
        e = self._entry(
            title="Safari Helper",
            keywords=["safari", "tabs"],
            id="safari-helper",
            description="manage safari",
            category="safari-tools",
        )
        assert macli._kb_score(e, ["safari"]) == 3.0 + 2.5 + 1.5 + 1.0 + 0.5

    def test_no_match_returns_zero(self, macli):
        e = self._entry(title="Calendar Events")
        assert macli._kb_score(e, ["safari"]) == 0.0

    def test_empty_query_returns_zero(self, macli):
        e = self._entry(title="Safari Helper")
        assert macli._kb_score(e, []) == 0.0

    def test_multi_token_query_sums(self, macli):
        e = self._entry(title="Safari Tabs Helper")
        # both "safari" and "tabs" hit title → 3 + 3 = 6
        assert macli._kb_score(e, ["safari", "tabs"]) == 6.0

    def test_score_only_counts_field_once_per_token(self, macli):
        # title text has "safari" twice but field is a set → 3.0 not 6.0
        e = self._entry(title="Safari Safari Safari")
        assert macli._kb_score(e, ["safari"]) == 3.0

    def test_missing_fields_treated_as_empty(self, macli):
        # An entry with only an id should not blow up
        e = {"id": "only_id"}
        assert macli._kb_score(e, ["only_id"]) == 1.5

    def test_none_keywords_handled(self, macli):
        # entry.get("keywords") could be None for partial data
        e = self._entry(keywords=None, title="hello")
        assert macli._kb_score(e, ["hello"]) == 3.0

    def test_ranking_title_beats_keyword(self, macli):
        a = self._entry(title="safari")
        b = self._entry(keywords=["safari"])
        assert macli._kb_score(a, ["safari"]) > macli._kb_score(b, ["safari"])


# ---------------------------------------------------------------------------
# _kb_newest_mtime
# ---------------------------------------------------------------------------

class TestNewestMtime:
    def test_empty_dir_returns_zero(self, macli, tmp_path):
        assert macli._kb_newest_mtime(tmp_path) == 0.0

    def test_single_md_file_mtime(self, macli, tmp_path):
        f = tmp_path / "a.md"
        f.write_text("---\nid: x\n---\n")
        expected = f.stat().st_mtime
        assert macli._kb_newest_mtime(tmp_path) == expected

    def test_picks_newest_recursively(self, macli, tmp_path):
        old = tmp_path / "sub" / "old.md"
        old.parent.mkdir()
        old.write_text("---\nid: old\n---\n")
        # Force older mtime
        os.utime(old, (1000, 1000))

        new = tmp_path / "deeper" / "newer.md"
        new.parent.mkdir()
        new.write_text("---\nid: new\n---\n")
        os.utime(new, (2_000_000, 2_000_000))

        assert macli._kb_newest_mtime(tmp_path) == 2_000_000.0

    def test_ignores_non_md_files(self, macli, tmp_path):
        (tmp_path / "ignore.txt").write_text("not md")
        (tmp_path / "data.json").write_text("{}")
        assert macli._kb_newest_mtime(tmp_path) == 0.0


# ---------------------------------------------------------------------------
# _kb_build_search_index + _kb_load_search_index
# ---------------------------------------------------------------------------

def _make_kb(tmp_path: Path):
    """Build a small KB directory with three valid entries and one noise file."""
    kb = tmp_path / "kb"
    kb.mkdir()

    (kb / "a.md").write_text(
        "---\n"
        "id: a_script\n"
        "title: Apple Script Hello\n"
        "category: cat_a\n"
        "description: A hello-world AppleScript example.\n"
        "keywords:\n"
        "  - apple\n"
        "  - hello\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    sub = kb / "sub"
    sub.mkdir()
    (sub / "b.md").write_text(
        "---\n"
        "id: safari_tabs\n"
        "title: Open Safari Tabs\n"
        "category: safari_tools\n"
        "description: >-\n"
        "  Opens multiple Safari tabs from a list of URLs in the user's\n"
        "  current Safari window.\n"
        "keywords:\n"
        "  - safari\n"
        "  - tabs\n"
        "---\n",
        encoding="utf-8",
    )

    # Noise: no frontmatter — should be skipped
    (kb / "skip_me.md").write_text("# just markdown, no fm\n", encoding="utf-8")

    # Noise: frontmatter but no id — should be skipped
    (kb / "no_id.md").write_text(
        "---\ntitle: orphan\n---\n", encoding="utf-8"
    )

    return kb


class TestBuildIndex:
    def test_index_skips_files_without_id(self, macli, tmp_path):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        entries = macli._kb_build_search_index(kb, idx_path)
        ids = {e["id"] for e in entries}
        assert ids == {"a_script", "safari_tabs"}

    def test_index_file_written_with_kb_mtime(self, macli, tmp_path):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "out" / "idx.json"  # nested → mkdir parents=True
        macli._kb_build_search_index(kb, idx_path)
        assert idx_path.exists()
        cached = json.loads(idx_path.read_text(encoding="utf-8"))
        assert "kb_mtime" in cached
        assert "entries" in cached
        assert cached["kb_mtime"] >= 0
        assert len(cached["entries"]) == 2

    def test_entry_path_is_relative(self, macli, tmp_path):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        entries = macli._kb_build_search_index(kb, idx_path)
        for e in entries:
            assert not Path(e["path"]).is_absolute()
        paths = {e["path"] for e in entries}
        # Stored as relative — sub/b.md not /full/sub/b.md
        assert any(p.endswith("b.md") for p in paths)
        assert "a.md" in paths

    def test_round_trip_via_load(self, macli, tmp_path, monkeypatch):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        macli._kb_build_search_index(kb, idx_path)

        # Point macli's module-level globals at our tmp KB and index
        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", kb)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", idx_path)

        loaded = macli._kb_load_search_index()
        assert len(loaded) == 2
        ids = {e["id"] for e in loaded}
        assert ids == {"a_script", "safari_tabs"}


class TestLoadIndex:
    def test_missing_kb_dir_returns_empty(self, macli, tmp_path, monkeypatch):
        nonexistent = tmp_path / "does_not_exist"
        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", nonexistent)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", tmp_path / "idx.json")
        assert macli._kb_load_search_index() == []

    def test_missing_index_triggers_build(self, macli, tmp_path, monkeypatch):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", kb)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", idx_path)

        assert not idx_path.exists()
        entries = macli._kb_load_search_index()
        assert idx_path.exists(), "missing index should trigger a build"
        assert len(entries) == 2

    def test_corrupt_json_triggers_rebuild(self, macli, tmp_path, monkeypatch):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        idx_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", kb)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", idx_path)
        entries = macli._kb_load_search_index()
        # After rebuild the json should now be valid
        json.loads(idx_path.read_text(encoding="utf-8"))
        assert len(entries) == 2

    def test_stale_cache_triggers_rebuild(self, macli, tmp_path, monkeypatch):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        # Build, then write a stale cache (kb_mtime way in the past)
        macli._kb_build_search_index(kb, idx_path)
        stale = {"kb_mtime": 1.0, "entries": []}  # ancient mtime, empty
        idx_path.write_text(json.dumps(stale), encoding="utf-8")

        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", kb)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", idx_path)

        # KB has newer .md files than kb_mtime=1.0 → must rebuild
        entries = macli._kb_load_search_index()
        assert len(entries) == 2, \
            "stale cache must trigger rebuild and pick up live KB entries"

    def test_fresh_cache_not_rebuilt(self, macli, tmp_path, monkeypatch):
        kb = _make_kb(tmp_path)
        idx_path = tmp_path / "idx.json"
        macli._kb_build_search_index(kb, idx_path)

        # Capture the index file's mtime, then load — file should NOT be
        # rewritten because the cache is current.
        before = idx_path.stat().st_mtime
        # Push idx_path mtime well into the future to detect a write
        future = time.time() + 100
        os.utime(idx_path, (future, future))
        before = idx_path.stat().st_mtime

        monkeypatch.setattr(macli, "MACOS_AUTOMATOR_KB", kb)
        monkeypatch.setattr(macli, "KB_SEARCH_INDEX", idx_path)

        macli._kb_load_search_index()
        after = idx_path.stat().st_mtime
        assert after == before, "fresh cache should not be rewritten"


# ---------------------------------------------------------------------------
# Integration: score+sort with real-style entries
# ---------------------------------------------------------------------------

class TestSearchRanking:
    def test_title_match_outranks_description_match(self, macli):
        entries = [
            {"id": "x", "title": "Safari Tabs",
             "description": "manage tabs", "keywords": [], "category": ""},
            {"id": "y", "title": "Calendar",
             "description": "mentions safari in passing",
             "keywords": [], "category": ""},
        ]
        tokens = macli._kb_tokenize("safari")
        scored = sorted(
            ((macli._kb_score(e, tokens), e) for e in entries),
            key=lambda x: x[0], reverse=True,
        )
        assert scored[0][1]["id"] == "x"
        assert scored[0][0] > scored[1][0]

    def test_keyword_outranks_description(self, macli):
        a = {"id": "a", "title": "", "description": "",
             "keywords": ["safari"], "category": ""}
        b = {"id": "b", "title": "", "description": "safari word here",
             "keywords": [], "category": ""}
        tokens = ["safari"]
        assert macli._kb_score(a, tokens) > macli._kb_score(b, tokens)
