"""Theme primitives for ContextHarness.

This module defines the core data structures for theme management
in the web interface, following the same patterns as other primitives.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, Union


class ThemeType(Enum):
    """Supported theme types."""

    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"


class ThemeCategory(Enum):
    """Theme categories for organization."""

    SYSTEM = "system"
    CUSTOM = "custom"
    ACCESSIBILITY = "accessibility"


@dataclass(frozen=True)
class ThemeColors:
    """Color palette for a theme."""

    # Primary colors
    background: str
    foreground: str
    primary: str
    secondary: str

    # Status colors
    success: str
    warning: str
    error: str
    info: str

    # UI colors
    border: str
    muted: str
    accent: str

    # Code/syntax colors (optional)
    syntax_comment: Optional[str] = None
    syntax_string: Optional[str] = None
    syntax_keyword: Optional[str] = None
    syntax_function: Optional[str] = None

    def to_css_dict(self) -> Dict[str, str]:
        """Convert to CSS custom properties dictionary."""
        css_dict = {
            "--theme-background": self.background,
            "--theme-foreground": self.foreground,
            "--theme-primary": self.primary,
            "--theme-secondary": self.secondary,
            "--theme-success": self.success,
            "--theme-warning": self.warning,
            "--theme-error": self.error,
            "--theme-info": self.info,
            "--theme-border": self.border,
            "--theme-muted": self.muted,
            "--theme-accent": self.accent,
        }

        # Add syntax colors if they exist
        if self.syntax_comment:
            css_dict["--theme-syntax-comment"] = self.syntax_comment
        if self.syntax_string:
            css_dict["--theme-syntax-string"] = self.syntax_string
        if self.syntax_keyword:
            css_dict["--theme-syntax-keyword"] = self.syntax_keyword
        if self.syntax_function:
            css_dict["--theme-syntax-function"] = self.syntax_function

        return css_dict


@dataclass(frozen=True)
class ThemeMetadata:
    """Metadata about a theme."""

    name: str
    display_name: str
    description: str
    author: str
    version: str
    theme_type: ThemeType
    category: ThemeCategory

    # Accessibility info
    wcag_compliant: bool
    contrast_ratio: float  # Minimum contrast ratio for normal text

    # Visual characteristics
    has_transparency: bool = False
    supports_transitions: bool = True

    def __post_init__(self):
        """Validate metadata after initialization."""
        if not self.name:
            raise ValueError("Theme name cannot be empty")
        if not self.display_name:
            raise ValueError("Display name cannot be empty")
        if self.contrast_ratio < 1.0:
            raise ValueError("Contrast ratio must be >= 1.0")


@dataclass(frozen=True)
class Theme:
    """A complete theme definition."""

    metadata: ThemeMetadata
    colors: ThemeColors
    custom_css: Optional[str] = None  # Additional CSS rules

    def to_tailwind_palette(self) -> Dict[str, str]:
        """Convert to Tailwind CSS palette format."""
        return {
            "background": self.colors.background,
            "foreground": self.colors.foreground,
            "primary": self.colors.primary,
            "secondary": self.colors.secondary,
            "success": self.colors.success,
            "warning": self.colors.warning,
            "error": self.colors.error,
            "info": self.colors.info,
            "border": self.colors.border,
            "muted": self.colors.muted,
            "accent": self.colors.accent,
        }

    def validate_contrast(self) -> Union[Tuple[str, float], Tuple[str, str]]:
        """Validate that key color combinations meet contrast requirements.

        Returns:
            Tuple of (message, contrast_ratio) for success
            Tuple of (error_message, "error") for failure
        """
        # This is a simplified validation - in practice, you'd want
        # more sophisticated contrast checking
        try:
            # Check background vs foreground (most critical)
            from colorsys import rgb_to_hls, hls_to_rgb

            def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
                hex_color = hex_color.lstrip("#")
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b)

            def get_luminance(hex_color: str) -> float:
                r, g, b = hex_to_rgb(hex_color)
                # Convert to 0-1 range
                r, g, b = r / 255.0, g / 255.0, b / 255.0
                # Apply gamma correction
                r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
                g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
                b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
                # Calculate luminance
                return 0.2126 * r + 0.7152 * g + 0.0722 * b

            def get_contrast(color1: str, color2: str) -> float:
                l1 = get_luminance(color1)
                l2 = get_luminance(color2)
                lighter = max(l1, l2)
                darker = min(l1, l2)
                return (lighter + 0.05) / (darker + 0.05)

            # Check critical contrast pairs
            bg_fg_contrast = get_contrast(
                self.colors.background, self.colors.foreground
            )

            if bg_fg_contrast < 4.5:  # WCAG AA requirement
                return (
                    f"Background/foreground contrast too low: {bg_fg_contrast:.2f} (needs 4.5+)",
                    bg_fg_contrast,
                )

            return ("Contrast validation passed", bg_fg_contrast)

        except Exception as e:
            return (f"Error validating contrast: {str(e)}", 0.0)


@dataclass(frozen=True)
class ThemePreference:
    """User's theme preferences."""

    theme_name: str
    auto_switch: bool = False  # Follow system preference
    transition_duration: float = 0.3  # seconds

    def __post_init__(self):
        """Validate preference after initialization."""
        if not self.theme_name:
            raise ValueError("Theme name cannot be empty")
        if self.transition_duration < 0:
            raise ValueError("Transition duration must be non-negative")


class ThemeValidationError(Exception):
    """Raised when theme validation fails."""

    pass


__all__ = [
    "ThemeType",
    "ThemeCategory",
    "ThemeColors",
    "ThemeMetadata",
    "Theme",
    "ThemePreference",
    "ThemeValidationError",
]
