"""Theme routes for ContextHarness web interface."""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from context_harness.services.theme_service import ThemeService
from context_harness.primitives import Result, is_failure


# Pydantic models for API responses
class ThemeColorsResponse(BaseModel):
    background: str
    foreground: str
    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    info: str
    border: str
    muted: str
    accent: str
    syntax_comment: Optional[str] = None
    syntax_string: Optional[str] = None
    syntax_keyword: Optional[str] = None
    syntax_function: Optional[str] = None


class ThemeMetadataResponse(BaseModel):
    name: str
    display_name: str
    description: str
    author: str
    version: str
    theme_type: str
    category: str
    wcag_compliant: bool
    contrast_ratio: float
    has_transparency: bool
    supports_transitions: bool


class ThemeResponse(BaseModel):
    metadata: ThemeMetadataResponse
    colors: ThemeColorsResponse
    custom_css: Optional[str] = None


class ThemePreferenceRequest(BaseModel):
    theme_name: str
    auto_switch: bool = False
    transition_duration: float = 0.3


def theme_to_response(theme) -> ThemeResponse:
    """Convert theme primitive to API response."""
    return ThemeResponse(
        metadata=ThemeMetadataResponse(
            name=theme.metadata.name,
            display_name=theme.metadata.display_name,
            description=theme.metadata.description,
            author=theme.metadata.author,
            version=theme.metadata.version,
            theme_type=theme.metadata.theme_type.value,
            category=theme.metadata.category.value,
            wcag_compliant=theme.metadata.wcag_compliant,
            contrast_ratio=theme.metadata.contrast_ratio,
            has_transparency=theme.metadata.has_transparency,
            supports_transitions=theme.metadata.supports_transitions,
        ),
        colors=ThemeColorsResponse(
            background=theme.colors.background,
            foreground=theme.colors.foreground,
            primary=theme.colors.primary,
            secondary=theme.colors.secondary,
            success=theme.colors.success,
            warning=theme.colors.warning,
            error=theme.colors.error,
            info=theme.colors.info,
            border=theme.colors.border,
            muted=theme.colors.muted,
            accent=theme.colors.accent,
            syntax_comment=theme.colors.syntax_comment,
            syntax_string=theme.colors.syntax_string,
            syntax_keyword=theme.colors.syntax_keyword,
            syntax_function=theme.colors.syntax_function,
        ),
        custom_css=theme.custom_css,
    )


def create_theme_router(theme_service: ThemeService) -> APIRouter:
    """Create theme router with all theme-related endpoints."""

    router = APIRouter(prefix="/api/themes", tags=["themes"])

    @router.get("/", response_model=List[ThemeResponse])
    async def get_all_themes(
        type: Optional[str] = Query(None, description="Filter by theme type"),
        category: Optional[str] = Query(None, description="Filter by category"),
    ) -> List[ThemeResponse]:
        """Get all available themes.

        Args:
            type: Optional filter by theme type (light, dark, high_contrast)
            category: Optional filter by category (system, custom, accessibility)

        Returns:
            List of available themes
        """
        try:
            if type:
                from context_harness.primitives.theme import ThemeType

                theme_type = ThemeType(type)
                themes = theme_service.get_themes_by_type(theme_type)
            elif category:
                from context_harness.primitives.theme import ThemeCategory

                theme_category = ThemeCategory(category)
                themes = theme_service.get_themes_by_category(theme_category)
            else:
                themes = theme_service.get_all_themes()

            return [theme_to_response(theme) for theme in themes]

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to load themes: {str(e)}"
            )

    @router.get("/{theme_name}", response_model=ThemeResponse)
    async def get_theme(theme_name: str) -> ThemeResponse:
        """Get a specific theme by name.

        Args:
            theme_name: Name of the theme to retrieve

        Returns:
            Theme details

        Raises:
            404: Theme not found
        """
        theme = theme_service.get_theme(theme_name)
        if not theme:
            raise HTTPException(
                status_code=404, detail=f"Theme '{theme_name}' not found"
            )

        return theme_to_response(theme)

    @router.get("/{theme_name}/css")
    async def get_theme_css(theme_name: str) -> str:
        """Get CSS for a specific theme.

        Args:
            theme_name: Name of the theme

        Returns:
            CSS with theme variables applied
        """
        theme = theme_service.get_theme(theme_name)
        if not theme:
            raise HTTPException(
                status_code=404, detail=f"Theme '{theme_name}' not found"
            )

        # Generate CSS with theme variables
        css_dict = theme.colors.to_css_dict()
        css_lines = [":root {"]

        for prop, value in css_dict.items():
            css_lines.append(f"  {prop}: {value};")

        css_lines.append("}")

        # Add custom CSS if present
        if theme.custom_css:
            css_lines.append("")
            css_lines.append("/* Custom theme CSS */")
            css_lines.append(theme.custom_css)

        return "\n".join(css_lines)

    @router.post("/preferences")
    async def save_preference(
        request: ThemePreferenceRequest, user_id: str = "default"
    ) -> dict:
        """Save user theme preference.

        Args:
            request: Theme preference data
            user_id: User identifier (defaults to "default")

        Returns:
            Success confirmation
        """
        from context_harness.primitives.theme import ThemePreference

        preference = ThemePreference(
            theme_name=request.theme_name,
            auto_switch=request.auto_switch,
            transition_duration=request.transition_duration,
        )

        result = theme_service.save_preference(preference, user_id)

        from context_harness.primitives import is_failure

        if is_failure(result):
            raise HTTPException(status_code=400, detail=result.error)

        return {"success": True, "message": "Theme preference saved"}

    @router.get("/preferences/{user_id}")
    async def get_preference(user_id: str = "default") -> dict:
        """Get user theme preference.

        Args:
            user_id: User identifier (defaults to "default")

        Returns:
            Theme preference data or null
        """
        preference = theme_service.load_preference(user_id)

        if not preference:
            return {"preference": None}

        return {
            "preference": {
                "theme_name": preference.theme_name,
                "auto_switch": preference.auto_switch,
                "transition_duration": preference.transition_duration,
            }
        }

    @router.post("/validate")
    async def validate_theme(theme: ThemeResponse) -> dict:
        """Validate a theme for accessibility compliance.

        Args:
            theme: Theme data to validate

        Returns:
            Validation results
        """
        try:
            # Convert API response back to theme primitive for validation
            from context_harness.primitives.theme import (
                Theme,
                ThemeColors,
                ThemeMetadata,
                ThemeType,
                ThemeCategory,
            )

            theme_primitive = Theme(
                metadata=ThemeMetadata(
                    name=theme.metadata.name,
                    display_name=theme.metadata.display_name,
                    description=theme.metadata.description,
                    author=theme.metadata.author,
                    version=theme.metadata.version,
                    theme_type=ThemeType(theme.metadata.theme_type),
                    category=ThemeCategory(theme.metadata.category),
                    wcag_compliant=theme.metadata.wcag_compliant,
                    contrast_ratio=theme.metadata.contrast_ratio,
                    has_transparency=theme.metadata.has_transparency,
                    supports_transitions=theme.metadata.supports_transitions,
                ),
                colors=ThemeColors(
                    background=theme.colors.background,
                    foreground=theme.colors.foreground,
                    primary=theme.colors.primary,
                    secondary=theme.colors.secondary,
                    success=theme.colors.success,
                    warning=theme.colors.warning,
                    error=theme.colors.error,
                    info=theme.colors.info,
                    border=theme.colors.border,
                    muted=theme.colors.muted,
                    accent=theme.colors.accent,
                    syntax_comment=theme.colors.syntax_comment,
                    syntax_string=theme.colors.syntax_string,
                    syntax_keyword=theme.colors.syntax_keyword,
                    syntax_function=theme.colors.syntax_function,
                ),
                custom_css=theme.custom_css,
            )

            validation_result = theme_primitive.validate_contrast()

            if isinstance(validation_result, tuple) and validation_result[1] == "error":
                return {
                    "valid": False,
                    "error": validation_result[0],
                    "contrast_ratio": validation_result[1],
                }
            else:
                return {
                    "valid": True,
                    "message": validation_result[0],
                    "contrast_ratio": validation_result[1],
                    "wcag_compliant": validation_result[1]
                    >= 4.5,  # WCAG AA requirement
                }

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")

    return router
