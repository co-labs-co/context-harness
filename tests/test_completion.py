"""Tests for the completion module."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.shell_completion import CompletionItem

from context_harness.completion import (
    _fuzzy_match,
    _fuzzy_score,
    _get_cached_skills,
    _save_skills_to_cache,
    _fetch_skills_for_completion,
    complete_skill_names,
    clear_skills_cache,
    CACHE_DIR,
    SKILLS_CACHE_FILE,
    CACHE_TTL_SECONDS,
)


class TestFuzzyMatch:
    """Tests for fuzzy matching algorithm."""

    def test_fuzzy_match_exact(self):
        """Test exact match."""
        assert _fuzzy_match("react-forms", "react-forms") is True

    def test_fuzzy_match_prefix(self):
        """Test prefix match."""
        assert _fuzzy_match("react", "react-forms") is True

    def test_fuzzy_match_fuzzy(self):
        """Test fuzzy pattern matching."""
        assert _fuzzy_match("rf", "react-forms") is True
        assert _fuzzy_match("dja", "django-auth") is True
        assert _fuzzy_match("rfs", "react-forms") is True

    def test_fuzzy_match_case_insensitive(self):
        """Test case insensitive matching."""
        assert _fuzzy_match("RF", "react-forms") is True
        assert _fuzzy_match("react", "React-Forms") is True

    def test_fuzzy_match_no_match(self):
        """Test non-matching patterns."""
        assert _fuzzy_match("xyz", "react-forms") is False
        assert _fuzzy_match("abc", "django-auth") is False

    def test_fuzzy_match_empty_pattern(self):
        """Test empty pattern matches everything."""
        assert _fuzzy_match("", "react-forms") is True
        assert _fuzzy_match("", "anything") is True

    def test_fuzzy_match_pattern_longer_than_text(self):
        """Test pattern longer than text doesn't match."""
        assert _fuzzy_match("react-forms-extended", "react") is False

    def test_fuzzy_match_special_characters(self):
        """Test matching with hyphens and underscores."""
        assert _fuzzy_match("r-f", "react-forms") is True
        assert _fuzzy_match("r_f", "react_forms") is True


class TestFuzzyScore:
    """Tests for fuzzy scoring algorithm."""

    def test_fuzzy_score_exact_prefix(self):
        """Test exact prefix gets highest score."""
        score = _fuzzy_score("react", "react-forms")
        assert score > 1000  # Prefix match bonus

    def test_fuzzy_score_prefix_shorter_name_higher(self):
        """Test shorter names rank higher for same prefix."""
        score_short = _fuzzy_score("react", "react")
        score_long = _fuzzy_score("react", "react-forms-validation")
        assert score_short > score_long

    def test_fuzzy_score_no_match_zero(self):
        """Test non-matching patterns get zero score."""
        assert _fuzzy_score("xyz", "react-forms") == 0

    def test_fuzzy_score_empty_pattern(self):
        """Test empty pattern gets minimal score."""
        score = _fuzzy_score("", "react-forms")
        assert score == 1

    def test_fuzzy_score_contiguous_bonus(self):
        """Test contiguous matches get bonus."""
        # "rea" matches contiguously at start
        score_contiguous = _fuzzy_score("rea", "react-forms")
        # "r-a" matches but not contiguously
        score_sparse = _fuzzy_score("rfs", "react-forms")
        # Both should match but contiguous should score higher
        assert score_contiguous > 0
        assert score_sparse > 0

    def test_fuzzy_score_word_boundary_bonus(self):
        """Test word boundary matches get bonus."""
        # Matches at word boundaries (after -)
        score = _fuzzy_score("rf", "react-forms")
        assert score > 0


@pytest.fixture
def clean_cache(tmp_path, monkeypatch):
    """Set up a temporary cache directory."""
    cache_dir = tmp_path / "cache" / "context-harness"
    cache_file = cache_dir / "skills-cache.json"

    monkeypatch.setattr("context_harness.completion.CACHE_DIR", cache_dir)
    monkeypatch.setattr("context_harness.completion.SKILLS_CACHE_FILE", cache_file)

    yield cache_dir, cache_file

    # Cleanup
    if cache_file.exists():
        cache_file.unlink()


class TestCaching:
    """Tests for cache functionality."""

    def test_get_cached_skills_no_cache(self, clean_cache):
        """Test getting skills when no cache exists."""
        result = _get_cached_skills()
        assert result is None

    def test_save_and_get_cached_skills(self, clean_cache):
        """Test saving and retrieving skills from cache."""
        cache_dir, cache_file = clean_cache

        skills = [
            {"name": "skill-one", "description": "First skill"},
            {"name": "skill-two", "description": "Second skill"},
        ]

        _save_skills_to_cache(skills)

        assert cache_file.exists()

        cached = _get_cached_skills()
        assert cached == skills

    def test_get_cached_skills_expired(self, clean_cache, monkeypatch):
        """Test that expired cache returns None."""
        cache_dir, cache_file = clean_cache

        # Set a very short TTL for testing
        monkeypatch.setattr("context_harness.completion.CACHE_TTL_SECONDS", 1)

        skills = [{"name": "skill-one", "description": "First"}]
        _save_skills_to_cache(skills)

        # Wait for cache to expire
        time.sleep(1.5)

        result = _get_cached_skills()
        assert result is None

    def test_get_cached_skills_invalid_json(self, clean_cache):
        """Test handling of corrupted cache file."""
        cache_dir, cache_file = clean_cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("not valid json {", encoding="utf-8")

        result = _get_cached_skills()
        assert result is None

    def test_clear_skills_cache(self, clean_cache):
        """Test clearing the cache."""
        cache_dir, cache_file = clean_cache

        skills = [{"name": "skill", "description": "Test"}]
        _save_skills_to_cache(skills)

        assert cache_file.exists()

        result = clear_skills_cache()
        assert result is True
        assert not cache_file.exists()

    def test_clear_skills_cache_no_file(self, clean_cache):
        """Test clearing cache when no file exists."""
        result = clear_skills_cache()
        assert result is False


class TestFetchSkillsForCompletion:
    """Tests for fetching skills for completion."""

    @pytest.fixture
    def mock_registry(self):
        """Sample registry data."""
        return {
            "skills": [
                {"name": "react-forms", "description": "React form handling"},
                {"name": "django-auth", "description": "Django authentication"},
                {"name": "fastapi-crud", "description": "FastAPI CRUD patterns"},
            ]
        }

    def test_fetch_skills_from_cache(self, clean_cache, monkeypatch):
        """Test that cached skills are used when available."""
        cache_dir, cache_file = clean_cache

        skills = [{"name": "cached-skill", "description": "From cache"}]
        _save_skills_to_cache(skills)

        # Mock get_skills_registry to ensure it's not called
        mock_registry = MagicMock()

        with patch("context_harness.skills.get_skills_registry", mock_registry):
            result = _fetch_skills_for_completion()

        assert result == skills
        mock_registry.assert_not_called()

    def test_fetch_skills_from_registry(self, clean_cache, mock_registry):
        """Test fetching skills from registry when cache is empty."""
        with patch(
            "context_harness.skills.get_skills_registry",
            return_value=mock_registry,
        ):
            result = _fetch_skills_for_completion()

        assert len(result) == 3
        assert result[0]["name"] == "react-forms"

    def test_fetch_skills_registry_error(self, clean_cache):
        """Test handling registry fetch errors."""
        with patch(
            "context_harness.skills.get_skills_registry",
            return_value=None,
        ):
            result = _fetch_skills_for_completion()

        assert result == []

    def test_fetch_skills_caches_result(self, clean_cache, mock_registry):
        """Test that fetched skills are cached."""
        cache_dir, cache_file = clean_cache

        with patch(
            "context_harness.skills.get_skills_registry",
            return_value=mock_registry,
        ):
            _fetch_skills_for_completion()

        assert cache_file.exists()
        cached = _get_cached_skills()
        assert len(cached) == 3


class TestCompleteSkillNames:
    """Tests for the complete_skill_names function."""

    @pytest.fixture
    def mock_skills(self, monkeypatch):
        """Mock skills data for completion tests."""
        skills = [
            {"name": "react-forms", "description": "React form handling"},
            {"name": "react-router", "description": "React routing patterns"},
            {"name": "django-auth", "description": "Django authentication"},
            {"name": "django-rest", "description": "Django REST framework"},
            {"name": "fastapi-crud", "description": "FastAPI CRUD patterns"},
        ]

        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: skills,
        )

        return skills

    def test_complete_empty_input(self, mock_skills):
        """Test completion with empty input returns all skills."""
        completions = complete_skill_names(None, None, "")

        assert len(completions) == 5
        # Should return CompletionItem objects
        assert all(isinstance(c, CompletionItem) for c in completions)

    def test_complete_prefix_match(self, mock_skills):
        """Test completion with prefix match."""
        completions = complete_skill_names(None, None, "react")

        assert len(completions) == 2
        names = [c.value for c in completions]
        assert "react-forms" in names
        assert "react-router" in names

    def test_complete_fuzzy_match(self, mock_skills):
        """Test completion with fuzzy match."""
        completions = complete_skill_names(None, None, "rf")

        # Should match react-forms and react-router (r...f in forms)
        assert len(completions) >= 1
        names = [c.value for c in completions]
        assert "react-forms" in names

    def test_complete_no_match(self, mock_skills):
        """Test completion with no matching skills."""
        completions = complete_skill_names(None, None, "xyz")

        assert len(completions) == 0

    def test_complete_case_insensitive(self, mock_skills):
        """Test completion is case insensitive."""
        completions_lower = complete_skill_names(None, None, "react")
        completions_upper = complete_skill_names(None, None, "REACT")

        assert len(completions_lower) == len(completions_upper)

    def test_complete_includes_help_text(self, mock_skills):
        """Test completions include description as help text."""
        completions = complete_skill_names(None, None, "django")

        assert len(completions) == 2
        # Check that help text is included
        django_auth = next(c for c in completions if c.value == "django-auth")
        assert django_auth.help == "Django authentication"

    def test_complete_truncates_long_descriptions(self, monkeypatch):
        """Test that long descriptions are truncated."""
        long_desc = "A" * 100  # 100 character description
        skills = [{"name": "long-desc", "description": long_desc}]

        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: skills,
        )

        completions = complete_skill_names(None, None, "")

        assert len(completions) == 1
        assert len(completions[0].help) <= 53  # 50 + "..."

    def test_complete_empty_skills_list(self, monkeypatch):
        """Test completion with empty skills list."""
        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: [],
        )

        completions = complete_skill_names(None, None, "anything")
        assert completions == []

    def test_complete_skills_sorted_by_score(self, mock_skills):
        """Test that completions are sorted by match score."""
        completions = complete_skill_names(None, None, "react-forms")

        # Exact match should be first
        assert completions[0].value == "react-forms"

    def test_complete_handles_missing_name(self, monkeypatch):
        """Test handling of skill entries without name."""
        skills = [
            {"name": "valid-skill", "description": "Valid"},
            {"description": "No name"},  # Missing name field
            {"name": "", "description": "Empty name"},  # Empty name
        ]

        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: skills,
        )

        completions = complete_skill_names(None, None, "")

        # Should only include the valid skill
        assert len(completions) == 1
        assert completions[0].value == "valid-skill"


class TestShellCompletionIntegration:
    """Integration tests for shell completion with CLI."""

    def test_skill_install_has_completion(self):
        """Test that skill install command accepts shell_complete."""
        from context_harness.cli import skill_install_cmd

        # Check that the command has the skill_name parameter with completion
        params = skill_install_cmd.params
        skill_name_param = next(p for p in params if p.name == "skill_name")

        assert skill_name_param.shell_complete is not None

    def test_skill_install_argument_is_optional(self):
        """Test that skill_name argument is optional for interactive mode."""
        from context_harness.cli import skill_install_cmd

        params = skill_install_cmd.params
        skill_name_param = next(p for p in params if p.name == "skill_name")

        assert skill_name_param.required is False


class TestInteractiveSkillPicker:
    """Tests for interactive skill picker."""

    def test_interactive_picker_returns_none_on_no_skills(self, monkeypatch):
        """Test picker returns None when no skills available."""
        from io import StringIO
        from unittest.mock import MagicMock

        from context_harness.completion import interactive_skill_picker

        # Mock fetch to return empty list
        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: [],
        )

        # Mock console
        mock_console = MagicMock()
        mock_console.status.return_value.__enter__ = MagicMock()
        mock_console.status.return_value.__exit__ = MagicMock()

        result = interactive_skill_picker(mock_console)

        assert result is None

    def test_interactive_picker_builds_choices(self, monkeypatch):
        """Test picker builds correct choices from skills."""
        from unittest.mock import MagicMock, patch

        from context_harness.completion import interactive_skill_picker

        skills = [
            {"name": "skill-one", "description": "First skill"},
            {"name": "skill-two", "description": "Second skill"},
        ]

        monkeypatch.setattr(
            "context_harness.completion._fetch_skills_for_completion",
            lambda: skills,
        )

        mock_console = MagicMock()
        mock_console.status.return_value.__enter__ = MagicMock()
        mock_console.status.return_value.__exit__ = MagicMock()

        # Mock questionary at the module level (it's imported inside the function)
        with patch.dict("sys.modules", {"questionary": MagicMock()}) as mock_modules:
            import sys

            mock_q = sys.modules["questionary"]
            mock_select = MagicMock()
            mock_select.ask.return_value = "skill-one"
            mock_q.select.return_value = mock_select
            mock_q.Choice = lambda title, value: {"title": title, "value": value}
            mock_q.Style = MagicMock()

            result = interactive_skill_picker(mock_console)

            # Verify questionary.select was called
            mock_q.select.assert_called_once()
            assert result == "skill-one"


class TestInteractiveLocalSkillPicker:
    """Tests for interactive local skill picker."""

    def test_local_picker_returns_none_on_no_skills(self, monkeypatch, tmp_path):
        """Test picker returns None when no local skills available."""
        from unittest.mock import MagicMock

        from context_harness.completion import interactive_local_skill_picker

        # Create empty .opencode/skill directory
        skill_dir = tmp_path / ".opencode" / "skill"
        skill_dir.mkdir(parents=True, exist_ok=True)

        mock_console = MagicMock()

        result = interactive_local_skill_picker(mock_console, source_path=str(tmp_path))

        assert result is None

    def test_local_picker_returns_none_on_no_directory(self, monkeypatch, tmp_path):
        """Test picker returns None when skill directory doesn't exist."""
        from unittest.mock import MagicMock

        from context_harness.completion import interactive_local_skill_picker

        mock_console = MagicMock()

        result = interactive_local_skill_picker(mock_console, source_path=str(tmp_path))

        assert result is None

    def test_local_picker_filters_invalid_skills(self, monkeypatch, tmp_path):
        """Test picker only shows valid skills."""
        from unittest.mock import MagicMock, patch

        from context_harness.completion import interactive_local_skill_picker

        # Create skill directory with one valid and one invalid skill
        skill_dir = tmp_path / ".opencode" / "skill"

        # Valid skill with SKILL.md
        valid_skill = skill_dir / "valid-skill"
        valid_skill.mkdir(parents=True, exist_ok=True)
        (valid_skill / "SKILL.md").write_text(
            "---\nname: valid-skill\ndescription: A valid skill\n---\n# Valid Skill",
            encoding="utf-8",
        )

        # Invalid skill without SKILL.md
        invalid_skill = skill_dir / "invalid-skill"
        invalid_skill.mkdir(parents=True, exist_ok=True)

        mock_console = MagicMock()

        with patch.dict("sys.modules", {"questionary": MagicMock()}) as mock_modules:
            import sys

            mock_q = sys.modules["questionary"]
            mock_select = MagicMock()
            mock_select.ask.return_value = "valid-skill"
            mock_q.select.return_value = mock_select
            mock_q.Choice = lambda title, value: {"title": title, "value": value}
            mock_q.Style = MagicMock()

            result = interactive_local_skill_picker(
                mock_console, source_path=str(tmp_path)
            )

            # Should return the valid skill
            assert result == "valid-skill"

            # Verify only one choice was built (the valid skill)
            call_args = mock_q.select.call_args
            choices = call_args.kwargs.get(
                "choices", call_args.args[1] if len(call_args.args) > 1 else []
            )
            assert len(choices) == 1

    def test_local_picker_builds_choices_correctly(self, monkeypatch, tmp_path):
        """Test picker builds correct choices from local skills."""
        from unittest.mock import MagicMock, patch

        from context_harness.completion import interactive_local_skill_picker

        skill_dir = tmp_path / ".opencode" / "skill"

        # Create two valid skills
        skill_one = skill_dir / "skill-one"
        skill_one.mkdir(parents=True, exist_ok=True)
        (skill_one / "SKILL.md").write_text(
            "---\nname: skill-one\ndescription: First skill\n---\n# Skill One",
            encoding="utf-8",
        )

        skill_two = skill_dir / "skill-two"
        skill_two.mkdir(parents=True, exist_ok=True)
        (skill_two / "SKILL.md").write_text(
            "---\nname: skill-two\ndescription: Second skill\n---\n# Skill Two",
            encoding="utf-8",
        )

        mock_console = MagicMock()

        with patch.dict("sys.modules", {"questionary": MagicMock()}) as mock_modules:
            import sys

            mock_q = sys.modules["questionary"]
            mock_select = MagicMock()
            mock_select.ask.return_value = "skill-two"
            mock_q.select.return_value = mock_select
            mock_q.Choice = lambda title, value: {"title": title, "value": value}
            mock_q.Style = MagicMock()

            result = interactive_local_skill_picker(
                mock_console, source_path=str(tmp_path)
            )

            # Verify questionary.select was called
            mock_q.select.assert_called_once()
            assert result == "skill-two"

    def test_local_picker_returns_none_on_cancel(self, monkeypatch, tmp_path):
        """Test picker returns None when user cancels."""
        from unittest.mock import MagicMock, patch

        from context_harness.completion import interactive_local_skill_picker

        skill_dir = tmp_path / ".opencode" / "skill"
        skill_one = skill_dir / "skill-one"
        skill_one.mkdir(parents=True, exist_ok=True)
        (skill_one / "SKILL.md").write_text(
            "---\nname: skill-one\ndescription: First skill\n---\n# Skill One",
            encoding="utf-8",
        )

        mock_console = MagicMock()

        with patch.dict("sys.modules", {"questionary": MagicMock()}) as mock_modules:
            import sys

            mock_q = sys.modules["questionary"]
            mock_select = MagicMock()
            mock_select.ask.return_value = None  # User cancelled
            mock_q.select.return_value = mock_select
            mock_q.Choice = lambda title, value: {"title": title, "value": value}
            mock_q.Style = MagicMock()

            result = interactive_local_skill_picker(
                mock_console, source_path=str(tmp_path)
            )

            assert result is None


class TestSkillExtractHasOptionalArgument:
    """Test that skill extract command has optional skill_name argument."""

    def test_skill_extract_argument_is_optional(self):
        """Test that skill_name argument is optional for interactive mode."""
        from context_harness.cli import skill_extract_cmd

        params = skill_extract_cmd.params
        skill_name_param = next(p for p in params if p.name == "skill_name")

        assert skill_name_param.required is False
