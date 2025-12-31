"""Theme service for ContextHarness web interface.

Handles theme management, persistence, and validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Success,
    Result,
)
from context_harness.primitives.theme import (
    Theme,
    ThemeCategory,
    ThemeColors,
    ThemeMetadata,
    ThemePreference,
    ThemeType,
    ThemeValidationError,
)


class ThemeService:
    """Service for managing web UI themes.

    This service handles:
    - Loading and managing available themes
    - Saving and loading user preferences
    - Validating theme accessibility
    - Converting themes for web usage
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize theme service.

        Args:
            config_path: Path to theme configuration directory.
                        Uses .context-harness/themes/ by default.
        """
        if config_path is None:
            config_path = Path.cwd() / ".context-harness" / "themes"

        self.config_path = config_path
        self.config_path.mkdir(parents=True, exist_ok=True)

        # Cache for loaded themes
        self._themes: Dict[str, Theme] = {}

        # Load built-in themes
        self._load_builtin_themes()

        # Load custom themes from disk
        self._load_custom_themes()

    def _load_builtin_themes(self) -> None:
        """Load built-in themes."""

        # Solarized Light (specifically requested)
        solarized_light = Theme(
            metadata=ThemeMetadata(
                name="solarized_light",
                display_name="Solarized Light",
                description="Warm, eye-friendly theme designed by Ethan Schoonover",
                author="Ethan Schoonover",
                version="1.0.0",
                theme_type=ThemeType.LIGHT,
                category=ThemeCategory.SYSTEM,
                wcag_compliant=True,
                contrast_ratio=7.0,
                has_transparency=False,
                supports_transitions=True,
            ),
            colors=ThemeColors(
                background="#fdf6e3",
                foreground="#657b83",
                primary="#268bd2",
                secondary="#93a1a1",
                success="#859900",
                warning="#b58900",
                error="#dc322f",
                info="#2aa198",
                border="#93a1a1",
                muted="#839496",
                accent="#268bd2",
                syntax_comment="#93a1a1",
                syntax_string="#2aa198",
                syntax_keyword="#268bd2",
                syntax_function="#6c71c4",
            ),
        )

        # GitHub Dark
        github_dark = Theme(
            metadata=ThemeMetadata(
                name="github_dark",
                display_name="GitHub Dark",
                description="Official GitHub dark theme with excellent accessibility",
                author="GitHub",
                version="1.0.0",
                theme_type=ThemeType.DARK,
                category=ThemeCategory.SYSTEM,
                wcag_compliant=True,
                contrast_ratio=9.5,
                has_transparency=False,
                supports_transitions=True,
            ),
            colors=ThemeColors(
                background="#0d1117",
                foreground="#c9d1d9",
                primary="#58a6ff",
                secondary="#8b949e",
                success="#3fb950",
                warning="#d29922",
                error="#f85149",
                info="#58a6ff",
                border="#30363d",
                muted="#8b949e",
                accent="#58a6ff",
                syntax_comment="#8b949e",
                syntax_string="#a5d6ff",
                syntax_keyword="#ff7b72",
                syntax_function="#d2a8ff",
            ),
        )

        # Dracula Theme
        dracula = Theme(
            metadata=ThemeMetadata(
                name="dracula",
                display_name="Dracula",
                description="Vibrant purple-based theme with strong contrast",
                author="Zeno Rocha",
                version="1.0.0",
                theme_type=ThemeType.DARK,
                category=ThemeCategory.CUSTOM,
                wcag_compliant=True,
                contrast_ratio=8.2,
                has_transparency=False,
                supports_transitions=True,
            ),
            colors=ThemeColors(
                background="#282a36",
                foreground="#f8f8f2",
                primary="#bd93f9",
                secondary="#6272a4",
                success="#50fa7b",
                warning="#ffb86c",
                error="#ff5555",
                info="#8be9fd",
                border="#44475a",
                muted="#6272a4",
                accent="#bd93f9",
                syntax_comment="#6272a4",
                syntax_string="#f1fa8c",
                syntax_keyword="#ff79c6",
                syntax_function="#50fa7b",
            ),
        )

        # High Contrast
        high_contrast = Theme(
            metadata=ThemeMetadata(
                name="high_contrast",
                display_name="High Contrast",
                description="Maximum contrast theme for accessibility",
                author="ContextHarness",
                version="1.0.0",
                theme_type=ThemeType.HIGH_CONTRAST,
                category=ThemeCategory.ACCESSIBILITY,
                wcag_compliant=True,
                contrast_ratio=21.0,  # Maximum possible
                has_transparency=False,
                supports_transitions=True,
            ),
            colors=ThemeColors(
                background="#000000",
                foreground="#ffffff",
                primary="#ffff00",
                secondary="#cccccc",
                success="#00ff00",
                warning="#ff9900",
                error="#ff0000",
                info="#00ffff",
                border="#ffffff",
                muted="#cccccc",
                accent="#ffff00",
                syntax_comment="#cccccc",
                syntax_string="#00ff00",
                syntax_keyword="#ff00ff",
                syntax_function="#ffff00",
            ),
        )

        # Register built-in themes
        self._themes[solarized_light.metadata.name] = solarized_light
        self._themes[github_dark.metadata.name] = github_dark
        self._themes[dracula.metadata.name] = dracula
        self._themes[high_contrast.metadata.name] = high_contrast

    def _load_custom_themes(self) -> None:
        """Load custom themes from disk."""
        theme_files = self.config_path.glob("*.json")

        for theme_file in theme_files:
            try:
                with open(theme_file, "r") as f:
                    theme_data = json.load(f)

                theme = self._dict_to_theme(theme_data)
                self._themes[theme.metadata.name] = theme

            except Exception as e:
                # Log error but continue loading other themes
                print(f"Failed to load theme from {theme_file}: {e}")

    def _theme_to_dict(self, theme: Theme) -> Dict:
        """Convert theme to dictionary for serialization."""
        return {
            "metadata": {
                "name": theme.metadata.name,
                "display_name": theme.metadata.display_name,
                "description": theme.metadata.description,
                "author": theme.metadata.author,
                "version": theme.metadata.version,
                "theme_type": theme.metadata.theme_type.value,
                "category": theme.metadata.category.value,
                "wcag_compliant": theme.metadata.wcag_compliant,
                "contrast_ratio": theme.metadata.contrast_ratio,
                "has_transparency": theme.metadata.has_transparency,
                "supports_transitions": theme.metadata.supports_transitions,
            },
            "colors": {
                "background": theme.colors.background,
                "foreground": theme.colors.foreground,
                "primary": theme.colors.primary,
                "secondary": theme.colors.secondary,
                "success": theme.colors.success,
                "warning": theme.colors.warning,
                "error": theme.colors.error,
                "info": theme.colors.info,
                "border": theme.colors.border,
                "muted": theme.colors.muted,
                "accent": theme.colors.accent,
                "syntax_comment": theme.colors.syntax_comment,
                "syntax_string": theme.colors.syntax_string,
                "syntax_keyword": theme.colors.syntax_keyword,
                "syntax_function": theme.colors.syntax_function,
            },
            "custom_css": theme.custom_css,
        }

    def _dict_to_theme(self, data: Dict) -> Theme:
        """Convert dictionary to theme object."""
        metadata_data = data["metadata"]
        colors_data = data["colors"]

        metadata = ThemeMetadata(
            name=metadata_data["name"],
            display_name=metadata_data["display_name"],
            description=metadata_data["description"],
            author=metadata_data["author"],
            version=metadata_data["version"],
            theme_type=ThemeType(metadata_data["theme_type"]),
            category=ThemeCategory(metadata_data["category"]),
            wcag_compliant=metadata_data["wcag_compliant"],
            contrast_ratio=metadata_data["contrast_ratio"],
            has_transparency=metadata_data.get("has_transparency", False),
            supports_transitions=metadata_data.get("supports_transitions", True),
        )

        colors = ThemeColors(
            background=colors_data["background"],
            foreground=colors_data["foreground"],
            primary=colors_data["primary"],
            secondary=colors_data["secondary"],
            success=colors_data["success"],
            warning=colors_data["warning"],
            error=colors_data["error"],
            info=colors_data["info"],
            border=colors_data["border"],
            muted=colors_data["muted"],
            accent=colors_data["accent"],
            syntax_comment=colors_data.get("syntax_comment"),
            syntax_string=colors_data.get("syntax_string"),
            syntax_keyword=colors_data.get("syntax_keyword"),
            syntax_function=colors_data.get("syntax_function"),
        )

        return Theme(
            metadata=metadata,
            colors=colors,
            custom_css=data.get("custom_css"),
        )

    def get_all_themes(self) -> List[Theme]:
        """Get all available themes."""
        return list(self._themes.values())

    def get_theme(self, name: str) -> Optional[Theme]:
        """Get theme by name."""
        return self._themes.get(name)

    def get_themes_by_type(self, theme_type: ThemeType) -> List[Theme]:
        """Get themes filtered by type."""
        return [
            theme
            for theme in self._themes.values()
            if theme.metadata.theme_type == theme_type
        ]

    def get_themes_by_category(self, category: ThemeCategory) -> List[Theme]:
        """Get themes filtered by category."""
        return [
            theme
            for theme in self._themes.values()
            if theme.metadata.category == category
        ]

    def save_theme(self, theme: Theme) -> Result[Theme]:
        """Save a theme to disk.

        Args:
            theme: The theme to save

        Returns:
            Result indicating success or failure
        """
        try:
            # Validate theme first
            validation_result = theme.validate_contrast()
            if isinstance(validation_result, tuple) and validation_result[1] == "error":
                return Failure(
                    error=f"Theme validation failed: {validation_result[0]}",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            # Save to disk (for custom themes)
            theme_file = self.config_path / f"{theme.metadata.name}.json"
            with open(theme_file, "w") as f:
                json.dump(self._theme_to_dict(theme), f, indent=2)

            # Update cache
            self._themes[theme.metadata.name] = theme

            return Success(theme)

        except Exception as e:
            return Failure(
                error=f"Failed to save theme: {str(e)}", code=ErrorCode.CONFIG_INVALID
            )

    def delete_theme(self, name: str) -> Result[None]:
        """Delete a custom theme.

        Built-in themes cannot be deleted.

        Args:
            name: Name of theme to delete

        Returns:
            Result indicating success or failure
        """
        theme = self.get_theme(name)
        if not theme:
            return Failure(error=f"Theme '{name}' not found", code=ErrorCode.NOT_FOUND)

        # Don't allow deleting built-in themes
        if theme.metadata.category == ThemeCategory.SYSTEM:
            return Failure(
                error="Cannot delete built-in system themes",
                code=ErrorCode.PERMISSION_DENIED,
            )

        try:
            # Delete file
            theme_file = self.config_path / f"{name}.json"
            if theme_file.exists():
                theme_file.unlink()

            # Remove from cache
            del self._themes[name]

            return Success(None)

        except Exception as e:
            return Failure(
                error=f"Failed to delete theme: {str(e)}", code=ErrorCode.CONFIG_INVALID
            )

    def save_preference(
        self, preference: ThemePreference, user_id: str = "default"
    ) -> Result[ThemePreference]:
        """Save user theme preference.

        Args:
            preference: The theme preference to save
            user_id: User identifier (defaults to "default")

        Returns:
            Result indicating success or failure
        """
        try:
            pref_file = self.config_path / f"preferences_{user_id}.json"

            with open(pref_file, "w") as f:
                json.dump(
                    {
                        "theme_name": preference.theme_name,
                        "auto_switch": preference.auto_switch,
                        "transition_duration": preference.transition_duration,
                    },
                    f,
                    indent=2,
                )

            return Success(preference)

        except Exception as e:
            return Failure(
                error=f"Failed to save preference: {str(e)}",
                code=ErrorCode.CONFIG_INVALID,
            )

    def load_preference(self, user_id: str = "default") -> Optional[ThemePreference]:
        """Load user theme preference.

        Args:
            user_id: User identifier (defaults to "default")

        Returns:
            Theme preference if found, None otherwise
        """
        try:
            pref_file = self.config_path / f"preferences_{user_id}.json"

            if not pref_file.exists():
                return None

            with open(pref_file, "r") as f:
                data = json.load(f)

            return ThemePreference(
                theme_name=data["theme_name"],
                auto_switch=data.get("auto_switch", False),
                transition_duration=data.get("transition_duration", 0.3),
            )

        except Exception:
            return None
