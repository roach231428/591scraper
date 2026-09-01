"""Configuration and design tokens for the 591 scraper GUI application.

This module provides:
- Mode configuration for different scraper types
- Design token definitions (colors, themes)
- Theme management utilities
"""

import flet as ft
from typing import Dict


# ==========================================================
# Mode Configuration
# ==========================================================

MODES: Dict[str, dict] = {
    "租屋": {
        "collect_script": "collect_rent_list.py",
        "fetch_script": "fetch_rent_info.py",
        "url_placeholder": "https://rent.591.com.tw/...",
        "output_path": "cache/listings.jbl",
        "result_path": "cache/rent_results.csv",
    },
    "中古屋": {
        "collect_script": "collect_sale_list.py",
        "fetch_script": "fetch_sale_info.py",
        "url_placeholder": "https://sale.591.com.tw/...",
        "output_path": "cache/sale_listings.jbl",
        "result_path": "cache/sale_results.csv",
    },
}


# ==========================================================
# Design Tokens
# ==========================================================

# Accent colors (shared across all themes)
ACCENT_ORANGE = "#FF6B00"    # 591 brand orange
ACCENT_RED = "#F85149"       # Stop/error red
SUCCESS_GREEN = "#3FB950"    # Success green

# Theme definitions
THEMES: Dict[str, dict] = {
    "dark": {
        "bg_primary": "#0D1117",       # Deep navy black - main background
        "bg_surface": "#161B22",       # Slightly lighter - card surfaces
        "bg_input": "#161B22",         # Input fields - slightly lighter than bg_primary
        "bg_log": "#010409",           # Log console background
        "border_subtle": "#30363D",    # Subtle borders
        "border_focus": "#FF6B00",     # Focus border - 591 orange
        "text_primary": "#E6EDF3",     # Primary text
        "text_secondary": "#8B949E",   # Secondary text
        "text_muted": "#484F58",       # Muted text
        "status_idle": "#8B949E",      # Idle status color
        "status_running": "#FF6B00",   # Running status color
        "status_complete": "#3FB950",  # Complete status color
        "status_error": "#F85149",     # Error status color
    },
    "light": {
        "bg_primary": "#F6F8FA",       # Light gray - main background
        "bg_surface": "#FFFFFF",       # White - card surfaces
        "bg_input": "#FFFFFF",         # Input fields
        "bg_log": "#F6F8FA",           # Log console background
        "border_subtle": "#D0D7DE",    # Subtle borders
        "border_focus": "#FF6B00",     # Focus border - 591 orange
        "text_primary": "#1F2328",     # Primary text
        "text_secondary": "#656D76",   # Secondary text
        "text_muted": "#8C959F",       # Muted text
        "status_idle": "#656D76",      # Idle status color
        "status_running": "#FF6B00",   # Running status color
        "status_complete": "#1A7F37",  # Complete status color
        "status_error": "#CF222E",     # Error status color
    },
}


# ==========================================================
# Theme Manager
# ==========================================================

class ThemeManager:
    """Manages application theme state and color token retrieval."""

    def __init__(self, initial_theme: str = "system"):
        self._theme_value = initial_theme  # 'dark', 'light', or 'system'

    @property
    def value(self) -> str:
        return self._theme_value

    @value.setter
    def value(self, new_value: str):
        self._theme_value = new_value

    def get_theme_mode(self) -> ft.ThemeMode:
        """Convert theme value to Flet ThemeMode enum."""
        theme_map = {
            "dark": ft.ThemeMode.DARK,
            "light": ft.ThemeMode.LIGHT,
            "system": ft.ThemeMode.SYSTEM,
        }
        return theme_map.get(self._theme_value, ft.ThemeMode.DARK)

    def get_colors(self) -> Dict[str, str]:
        """Get color tokens based on current theme.

        Returns:
            Dictionary of color tokens including accent colors.
        """
        base = THEMES.get(
            "dark" if self._theme_value == "system" else self._theme_value,
            THEMES["dark"]
        )
        return {
            "bg_primary": base["bg_primary"],
            "bg_surface": base["bg_surface"],
            "bg_input": base["bg_input"],
            "bg_log": base["bg_log"],
            "border_subtle": base["border_subtle"],
            "border_focus": base["border_focus"],
            "text_primary": base["text_primary"],
            "text_secondary": base["text_secondary"],
            "text_muted": base["text_muted"],
            "status_idle": base["status_idle"],
            "status_running": base["status_running"],
            "status_complete": base["status_complete"],
            "status_error": base["status_error"],
            "accent_orange": ACCENT_ORANGE,
            "accent_red": ACCENT_RED,
            "success_green": SUCCESS_GREEN,
        }
