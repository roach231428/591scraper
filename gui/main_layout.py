"""Main layout components for the 591 scraper GUI application.

This module provides:
- Header component with theme selector
- Configuration panel (left side)
- Execution panel with log console (right side)
- Main split-panel layout
"""

import flet as ft
from typing import Dict

from gui.config import MODES
from gui.ui_components import (
    ModeDropdown,
    UrlField,
    MaxPagesField,
    PathField,
    QuietCheckbox,
    StatusIndicator,
    ActionButtons,
)
from gui.logger import LogConsoleManager


# ==========================================================
# Header Component
# ==========================================================

class Header(ft.Container):
    """Application header with logo and theme selector."""

    def __init__(self, theme_manager, on_theme_change=None):
        self.theme_manager = theme_manager
        self.colors = theme_manager.get_colors()

        self.logo_icon = ft.Icon(
            ft.Icons.HOME,
            size=20,
            color=self.colors["accent_orange"],
        )

        self.logo_icon_container = ft.Container(
            content=self.logo_icon,
            padding=6,
            bgcolor=self.colors["accent_orange"] + "15",
            border_radius=4,
        )

        self.logo_title = ft.Text(
            "591 房產爬蟲工具",
            size=16,
            weight=ft.FontWeight.W_600,
            color=self.colors["text_primary"],
        )

        self.theme_dropdown = self._build_theme_dropdown(
            on_theme_change
        )

        self.logo_container = self._build_logo()
        content = self._build_content()

        super().__init__(
            content=content,
            padding=ft.Padding.only(
                top=16,
                left=24,
                right=24,
                bottom=0,
            ),
            bgcolor=self.colors["bg_primary"],
        )

    def _build_theme_dropdown(self, on_theme_change=None) -> ft.Dropdown:
        """Create the theme selector."""
        dropdown = ft.Dropdown(
            label="主題",
            options=[
                ft.dropdown.Option("dark", "深色模式"),
                ft.dropdown.Option("light", "淺色模式"),
                ft.dropdown.Option("system", "跟隨系統"),
            ],
            value=self.theme_manager.value,
            expand=False,
            width=140,
        )

        if on_theme_change:
            dropdown.on_select = on_theme_change

        return dropdown

    def _build_logo(self) -> ft.Container:
        """Create the application logo."""
        return ft.Container(
            content=ft.Row(
                [
                    self.logo_icon_container,
                    ft.Container(width=8),
                    ft.Column(
                        [
                            self.logo_title,
                        ],
                        spacing=0,
                        tight=True,
                        wrap=False,
                    ),
                ],
                spacing=0,
                alignment=ft.MainAxisAlignment.START,
            ),
            expand=True,
        )

    def _build_content(self) -> ft.Row:
        """Build the complete header content."""
        return ft.Column(
            [
                ft.Row(
                    [
                        self.logo_container,
                        ft.Container(
                            content=self.theme_dropdown,
                            width=140,
                            alignment=ft.Alignment(0, 0.5),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                self._build_accent_line(),
            ],
            spacing=0,
            tight=True,
            expand=True,
        )

    def _build_accent_line(self) -> ft.Container:
        """Create the orange accent line."""
        return ft.Container(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Container(expand=1),
                        ft.Container(
                            content=ft.Text(
                                "591",
                                size=8,
                                color=self.colors["accent_orange"],
                                weight=ft.FontWeight.W_700,
                            ),
                            padding=ft.Padding.only(
                                left=4,
                                right=4,
                                top=1,
                                bottom=1,
                            ),
                        ),
                        ft.Container(expand=3),
                    ],
                ),
                bgcolor=self.colors["accent_orange"],
            ),
            height=3,
            expand=False,
        )

    def apply_theme(self, colors):
        """Apply the given theme colors."""
        self.colors = colors

        self.bgcolor = colors["bg_primary"]

        self.logo_icon.color = colors["accent_orange"]
        self.logo_icon_container.bgcolor = (
            colors["accent_orange"] + "15"
        )
        self.logo_title.color = colors["text_primary"]

        self.theme_dropdown.color = colors["text_primary"]
        self.theme_dropdown.label_style = ft.TextStyle(
            color=colors["text_secondary"]
        )
        self.theme_dropdown.hint_style = ft.TextStyle(
            color=colors["text_muted"]
        )


# ==========================================================
# Configuration Panel
# ==========================================================

class ConfigPanel(ft.Column):
    """Left panel containing scraper configuration."""

    DEFAULT_MAX_PAGES = 10

    def __init__(self, on_mode_change=None):
        self.mode_dropdown = ModeDropdown(on_select=on_mode_change)
        self.url_field = UrlField()
        self.max_pages_field = MaxPagesField()
        self.output_path_field = PathField(
            "Collect 輸出檔案路徑",
            "cache/listings.jbl",
        )
        self.result_path_field = PathField(
            "Fetch 結果檔案路徑",
            "cache/results.csv",
        )
        self.quiet_checkbox = QuietCheckbox()

        self._section_icon = ft.Icon(ft.Icons.TUNE, size=16)
        self._section_title = ft.Text(
            "設定",
            size=13,
            weight=ft.FontWeight.W_600,
        )
        self._info_button = ft.IconButton(
            icon=ft.Icons.INFO_OUTLINED,
            icon_size=14,
            tooltip="設定說明",
        )

        self._content = self._build_content()

        super().__init__(
            controls=[self._content],
            spacing=0,
            expand=True,
        )

    # ------------------------------------------------------
    # UI
    # ------------------------------------------------------

    def _build_content(self) -> ft.Column:
        return ft.Column(
            [
                self._build_section_header(),
                self._build_form(),
            ],
            spacing=0,
            expand=True,
        )

    def _build_section_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    self._section_icon,
                    ft.Container(width=8),
                    self._section_title,
                    ft.Container(width=8),
                    self._info_button,
                ],
                spacing=0,
            ),
            padding=ft.Padding.only(
                left=20,
                right=20,
                top=20,
                bottom=8,
            ),
        )

    def _build_form(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    self.mode_dropdown,
                    self.url_field,
                    self._build_output_row(),
                    self._build_result_section(),
                ],
                spacing=0,
                tight=True,
                expand=True,
            ),
            expand=True,
        )

    def _build_output_row(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=self.max_pages_field,
                        padding=ft.Padding.only(
                            left=20,
                            right=6,
                            bottom=12,
                        ),
                    ),
                    ft.Container(width=12),
                    ft.Container(
                        content=self.output_path_field,
                        expand=True,
                    ),
                ],
                spacing=0,
            ),
        )

    def _build_result_section(self) -> ft.Column:
        return ft.Column(
            [
                self.result_path_field,
                self.quiet_checkbox,
            ],
            spacing=4,
        )

    # ------------------------------------------------------
    # Theme
    # ------------------------------------------------------

    def apply_theme(self, colors):
        self._section_icon.color = colors["text_secondary"]
        self._section_title.color = colors["text_secondary"]
        self._info_button.icon_color = colors["text_muted"]

        for field in (
            self.mode_dropdown,
            self.url_field,
            self.max_pages_field,
            self.output_path_field,
            self.result_path_field,
            self.quiet_checkbox,
        ):
            field.apply_theme(colors)

    # ------------------------------------------------------
    # Configuration
    # ------------------------------------------------------

    def update_paths_for_mode(self, mode: str):
        config = MODES.get(mode)

        if not config:
            return

        self.url_field.hint_text = config["url_placeholder"]
        self.output_path_field.value = config["output_path"]
        self.result_path_field.value = config["result_path"]

    def get_config(self) -> Dict:
        mode = self.mode_dropdown.value
        config = MODES[mode].copy()

        config.update(
            mode=mode,
            url=self.url_field.value,
            max_pages=self._get_max_pages(),
            output_path=self.output_path_field.value,
            result_path=self.result_path_field.value,
            quiet=self.quiet_checkbox.value,
        )

        return config

    def _get_max_pages(self) -> int:
        try:
            return int(
                self.max_pages_field.value
                or self.DEFAULT_MAX_PAGES
            )
        except (TypeError, ValueError):
            return self.DEFAULT_MAX_PAGES


# ==========================================================
# Execution Panel
# ==========================================================

class ExecutionPanel(ft.Column):
    """Right panel for execution control and log display."""

    def __init__(
        self,
        log_console_manager: LogConsoleManager,
        on_start=None,
        on_stop=None,
        on_open_result=None,
    ):
        # --------------------------------------------------
        # Components
        # --------------------------------------------------

        self.status_indicator = StatusIndicator()

        self.action_buttons = ActionButtons(
            on_start=on_start,
            on_stop=on_stop,
            on_open_result=on_open_result,
        )

        # Section header
        self._section_icon = ft.Icon(
            ft.Icons.TERMINAL,
            size=16,
        )
        self._section_title = ft.Text(
            "執行控制台",
            size=13,
            weight=ft.FontWeight.W_600,
        )

        # Log console
        self._log_icon = ft.Icon(
            ft.Icons.DESKTOP_WINDOWS,
            size=12,
        )
        self._log_title = ft.Text(
            "執行日誌",
            size=11,
            weight=ft.FontWeight.W_500,
        )
        self._clear_logs_button = ft.IconButton(
            icon=ft.Icons.CLEANING_SERVICES,
            icon_size=14,
            tooltip="清除日誌",
            on_click=lambda _: log_console_manager.clear_logs(),
        )

        # Build UI
        self._log_container = self._build_log_console(
            log_console_manager
        )
        self._content = self._build_content()

        super().__init__(
            controls=[self._content],
            spacing=0,
            expand=True,
        )

    # ======================================================
    # UI
    # ======================================================

    def _build_content(self) -> ft.Column:
        """Build the complete execution panel."""
        return ft.Column(
            [
                self._build_section_header(),
                self.status_indicator,
                self.action_buttons,
                self._log_container,
            ],
            spacing=0,
            expand=True,
        )

    def _build_section_header(self) -> ft.Container:
        """Build the execution section header."""
        return ft.Container(
            content=ft.Row(
                [
                    self._section_icon,
                    ft.Container(width=8),
                    self._section_title,
                ],
                spacing=0,
            ),
            padding=ft.Padding.only(
                left=20,
                right=20,
                top=20,
                bottom=8,
            ),
        )

    def _build_log_console(
        self,
        log_console_manager: LogConsoleManager,
    ) -> ft.Container:
        """Build the log console container."""

        self._log_header = ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=12),
                    self._log_icon,
                    ft.Container(width=8),
                    self._log_title,
                    ft.Container(expand=True),
                    self._clear_logs_button,
                ],
                spacing=0,
            ),
            padding=ft.Padding.only(
                left=12,
                right=12,
                top=8,
                bottom=8,
            ),
            border_radius=ft.BorderRadius.only(
                top_left=4,
                top_right=4,
            ),
        )

        log_content = ft.Container(
            content=log_console_manager.log_console,
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    self._log_header,
                    log_content,
                ],
                spacing=0,
                expand=True,
            ),
            border=ft.Border.all(1, None),
            border_radius=4,
            padding=ft.Padding.only(top=0),
            expand=True,
        )

    # ======================================================
    # Theme
    # ======================================================

    def apply_theme(self, colors):
        """Apply the given theme colors to all components."""

        # Section header
        self._section_icon.color = colors["text_secondary"]
        self._section_title.color = colors["text_secondary"]

        # Status and action controls
        self.status_indicator.apply_theme(colors)
        self.action_buttons.apply_theme(colors)

        # Log console header
        self._log_header.bgcolor = colors["bg_surface"]
        self._log_icon.color = colors["text_muted"]
        self._log_title.color = colors["text_muted"]
        self._clear_logs_button.icon_color = colors["text_muted"]

        # Log console container
        self._log_container.border = ft.Border.all(
            1,
            colors["border_subtle"],
        )
        self._log_container.bgcolor = colors["bg_log"]

# ==========================================================
# Main Layout
# ==========================================================

class MainLayout(ft.Column):
    """Main application layout with header and split panels."""

    def __init__(
        self,
        theme_manager,
        config_panel,
        execution_panel,
        on_theme_change=None,
    ):
        header = Header(theme_manager, on_theme_change=on_theme_change)

        self._left_panel = ft.Container(
            content=config_panel,
            width=380,
            border=ft.Border.only(right=ft.border.BorderSide(1, None)),
            bgcolor=None,
        )
        self.right_panel = ft.Container(
            content=execution_panel,
            expand=True,
        )

        content = ft.Column(
            [
                header,
                ft.Row(
                    [
                        self._left_panel,
                        self.right_panel,
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )

        super().__init__(
            controls=[content],
            expand=True,
            spacing=0,
        )

        self._header = header
        self._config_panel = config_panel
        self._execution_panel = execution_panel

    def apply_theme(self, colors):
        """Apply current theme to all components."""
        self._header.apply_theme(colors)
        self._config_panel.apply_theme(colors)
        self._execution_panel.apply_theme(colors)

        # Update split panel borders
        self._left_panel.bgcolor = colors["bg_primary"]
        self._left_panel.border = ft.Border.only(right=ft.border.BorderSide(1, colors["border_subtle"]))
