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


# ---------------------------------------------------------------------------
# skill init-repo
# ---------------------------------------------------------------------------


class TestSkillInitRepoCommand:
    """Tests for `context-harness skill init-repo`."""

    def test_init_repo_success(self) -> None:
        """Successful creation → exit 0, 'created' in output."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 0
        assert "created" in result.output.lower()

    def test_init_repo_success_shows_url(self) -> None:
        """Successful creation shows the repository URL."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 0
        assert "https://github.com/test-user/my-skills" in result.output

    def test_init_repo_already_exists(self) -> None:
        """Repo already exists → exit 0 (informational), 'already exists' in output."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(SkillResult.ALREADY_EXISTS, None),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 0
        assert "already exists" in result.output.lower()

    def test_init_repo_auth_error(self) -> None:
        """Auth error → exit 1, 'authentication' in output."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(SkillResult.AUTH_ERROR, None),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 1
        assert "authentication" in result.output.lower()

    def test_init_repo_generic_error(self) -> None:
        """Generic error → exit 1."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(SkillResult.ERROR, None),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 1

    def test_init_repo_private_flag(self) -> None:
        """--private flag is passed through to init_repo."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ) as mock_init:
            runner.invoke(skill_group, ["init-repo", "my-skills", "--private"])

        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["private"] is True

    def test_init_repo_public_flag(self) -> None:
        """--public flag is passed through to init_repo."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ) as mock_init:
            runner.invoke(skill_group, ["init-repo", "my-skills", "--public"])

        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["private"] is False

    def test_init_repo_description_flag(self) -> None:
        """--description flag is passed through to init_repo."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ) as mock_init:
            runner.invoke(
                skill_group,
                ["init-repo", "my-skills", "--description", "Team AI skills"],
            )

        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["description"] == "Team AI skills"

    def test_init_repo_configure_user_flag(self) -> None:
        """--configure-user flag triggers user config update."""
        runner = CliRunner()

        with (
            patch(
                "context_harness.interfaces.cli.skill_cmd.init_repo",
                return_value=(
                    SkillResult.SUCCESS,
                    "https://github.com/test-user/my-skills",
                ),
            ),
            patch(
                "context_harness.interfaces.cli.skill_cmd._configure_skills_repo_user",
            ) as mock_configure,
        ):
            result = runner.invoke(
                skill_group, ["init-repo", "my-skills", "--configure-user"]
            )

        assert result.exit_code == 0
        mock_configure.assert_called_once_with("test-user/my-skills")

    def test_init_repo_configure_project_flag(self) -> None:
        """--configure-project flag triggers project config update."""
        runner = CliRunner()

        with (
            patch(
                "context_harness.interfaces.cli.skill_cmd.init_repo",
                return_value=(
                    SkillResult.SUCCESS,
                    "https://github.com/test-user/my-skills",
                ),
            ),
            patch(
                "context_harness.interfaces.cli.skill_cmd._configure_skills_repo_project",
            ) as mock_configure,
        ):
            result = runner.invoke(
                skill_group, ["init-repo", "my-skills", "--configure-project"]
            )

        assert result.exit_code == 0
        mock_configure.assert_called_once_with("test-user/my-skills")

    def test_init_repo_no_configure_shows_instructions(self) -> None:
        """Without --configure flags, shows manual configuration instructions."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/test-user/my-skills",
            ),
        ):
            result = runner.invoke(skill_group, ["init-repo", "my-skills"])

        assert result.exit_code == 0
        assert "skills-repo" in result.output.lower()

    def test_init_repo_name_is_required(self) -> None:
        """Missing NAME argument → error from Click."""
        runner = CliRunner()
        result = runner.invoke(skill_group, ["init-repo"])

        assert result.exit_code != 0

    def test_init_repo_org_name(self) -> None:
        """Owner/repo name format is accepted."""
        runner = CliRunner()

        with patch(
            "context_harness.interfaces.cli.skill_cmd.init_repo",
            return_value=(
                SkillResult.SUCCESS,
                "https://github.com/my-org/team-skills",
            ),
        ) as mock_init:
            result = runner.invoke(skill_group, ["init-repo", "my-org/team-skills"])

        assert result.exit_code == 0
        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["name"] == "my-org/team-skills"
