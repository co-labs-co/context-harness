"""Unit tests for skill CLI commands: outdated and upgrade."""

from __future__ import annotations

from typing import List, Optional
from unittest.mock import patch

from click.testing import CliRunner

from context_harness.interfaces.cli.skill_cmd import skill_group
from context_harness.primitives import VersionStatus
from context_harness.primitives.skill import VersionComparison
from context_harness.skills import SkillResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_comparison(
    skill_name: str = "test-skill",
    local_version: str = "1.0.0",
    remote_version: str = "2.0.0",
    status: VersionStatus = VersionStatus.UPGRADE_AVAILABLE,
    context_harness_min: Optional[str] = None,
    current_context_harness: str = "3.0.0",
) -> VersionComparison:
    return VersionComparison(
        skill_name=skill_name,
        local_version=local_version,
        remote_version=remote_version,
        status=status,
        context_harness_min=context_harness_min,
        current_context_harness=current_context_harness,
    )


# ---------------------------------------------------------------------------
# skill outdated
# ---------------------------------------------------------------------------


class TestSkillOutdatedCommand:
    """Tests for `context-harness skill outdated`."""

    def test_outdated_no_updates(self, tmp_path) -> None:
        """No outdated skills → success message, exit 0."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.SUCCESS, []),
        ):
            result = runner.invoke(skill_group, ["outdated", "--source", str(tmp_path)])

        assert result.exit_code == 0
        assert "up to date" in result.output.lower()

    def test_outdated_with_updates(self, tmp_path) -> None:
        """Outdated skills found → list printed, exit 0."""
        runner = CliRunner()
        comparisons = [
            _make_comparison("skill-a", "1.0.0", "2.0.0"),
            _make_comparison("skill-b", "0.5.0", "1.0.0"),
        ]

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.SUCCESS, comparisons),
        ):
            result = runner.invoke(skill_group, ["outdated", "--source", str(tmp_path)])

        assert result.exit_code == 0
        assert "2" in result.output  # "Found 2 skill(s)"

    def test_outdated_error_exits_1(self, tmp_path) -> None:
        """Error checking updates → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.ERROR, None),
        ):
            result = runner.invoke(skill_group, ["outdated", "--source", str(tmp_path)])

        assert result.exit_code == 1

    def test_outdated_incompatible_skill_shown(self, tmp_path) -> None:
        """Incompatible skill status shown in table."""
        runner = CliRunner()
        comparisons = [
            _make_comparison(
                "compat-skill",
                "1.0.0",
                "2.0.0",
                status=VersionStatus.INCOMPATIBLE,
                context_harness_min="99.0.0",
            )
        ]

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.SUCCESS, comparisons),
        ):
            result = runner.invoke(skill_group, ["outdated", "--source", str(tmp_path)])

        assert result.exit_code == 0
        assert "1" in result.output  # "Found 1 skill(s)"


# ---------------------------------------------------------------------------
# skill upgrade
# ---------------------------------------------------------------------------


class TestSkillUpgradeCommand:
    """Tests for `context-harness skill upgrade`."""

    def test_upgrade_no_name_no_all_exits_1(self, tmp_path) -> None:
        """No skill name and no --all flag → exit 1 with error message."""
        runner = CliRunner()
        result = runner.invoke(skill_group, ["upgrade", "--source", str(tmp_path)])
        assert result.exit_code == 1
        assert "skill name" in result.output.lower() or "--all" in result.output.lower()

    def test_upgrade_specific_skill_success(self, tmp_path) -> None:
        """Upgrade a named skill successfully → exit 0."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
            return_value=SkillResult.SUCCESS,
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "my-skill", "--source", str(tmp_path)],
            )

        assert result.exit_code == 0

    def test_upgrade_not_found_exits_1(self, tmp_path) -> None:
        """Upgrading a skill that doesn't exist locally → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
            return_value=SkillResult.NOT_FOUND,
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "ghost-skill", "--source", str(tmp_path)],
            )

        assert result.exit_code == 1

    def test_upgrade_auth_error_exits_1(self, tmp_path) -> None:
        """Auth error during upgrade → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
            return_value=SkillResult.AUTH_ERROR,
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "my-skill", "--source", str(tmp_path)],
            )

        assert result.exit_code == 1
        assert "authentication" in result.output.lower()

    def test_upgrade_generic_error_exits_1(self, tmp_path) -> None:
        """Generic error during upgrade → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
            return_value=SkillResult.ERROR,
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "my-skill", "--source", str(tmp_path)],
            )

        assert result.exit_code == 1

    def test_upgrade_all_no_outdated(self, tmp_path) -> None:
        """--all with no outdated skills → success, exit 0."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.SUCCESS, []),
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "--all", "--source", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert "up to date" in result.output.lower()

    def test_upgrade_all_upgrades_each_skill(self, tmp_path) -> None:
        """--all with outdated skills calls upgrade_skill for each."""
        runner = CliRunner()
        comparisons = [
            _make_comparison("skill-a"),
            _make_comparison("skill-b"),
        ]

        with (
            patch(
                "context_harness.interfaces.cli.skill_cmd.check_updates",
                return_value=(SkillResult.SUCCESS, comparisons),
            ) as mock_check,
            patch(
                "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
                return_value=SkillResult.SUCCESS,
            ) as mock_upgrade,
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "--all", "--source", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert mock_upgrade.call_count == 2

    def test_upgrade_all_check_error_exits_1(self, tmp_path) -> None:
        """--all when check_updates fails → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.check_updates",
            return_value=(SkillResult.ERROR, None),
        ):
            result = runner.invoke(
                skill_group,
                ["upgrade", "--all", "--source", str(tmp_path)],
            )

        assert result.exit_code == 1

    def test_upgrade_force_flag_passed_through(self, tmp_path) -> None:
        """--force flag is passed as force_compatibility=True to upgrade_skill."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.upgrade_skill",
            return_value=SkillResult.SUCCESS,
        ) as mock_upgrade:
            runner.invoke(
                skill_group,
                ["upgrade", "my-skill", "--force", "--source", str(tmp_path)],
            )

        mock_upgrade.assert_called_once()
        call_kwargs = mock_upgrade.call_args
        # force_compatibility should be True
        assert call_kwargs.kwargs.get("force_compatibility") is True or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] is True
        )
