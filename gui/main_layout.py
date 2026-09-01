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

        self.theme_dropdown = ft.Dropdown(
            label="主題",
            options=[
                ft.dropdown.Option("dark", "深色模式"),
                ft.dropdown.Option("light", "淺色模式"),
                ft.dropdown.Option("system", "跟隨系統"),
            ],
            value=theme_manager.value,
            expand=False,
            width=140,
            color=None,
            label_style=None,
            hint_style=None,
        )
        if on_theme_change:
            self.theme_dropdown.on_change = on_theme_change

        self.logo_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.HOME, size=20, color=self.colors["accent_orange"]),
                        padding=6,
                        bgcolor=self.colors["accent_orange"] + "15",
                        border_radius=4,
                    ),
                    ft.Container(width=8),
                    ft.Column(
                        [
                            ft.Text(
                                "591 房產爬蟲工具",
                                size=16,
                                weight=ft.FontWeight.W_600,
                                color=self.colors["text_primary"],
                            ),
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

        content = ft.Row(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                self.logo_container,
                                ft.Container(
                                    content=self.theme_dropdown,
                                    width=140,
                                    expand=True,
                                    alignment=ft.alignment.center_right,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            expand=True,
                        ),
                        ft.Container(
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
                                            padding=ft.padding.only(left=4, right=4, top=1, bottom=1),
                                        ),
                                        ft.Container(expand=3),
                                    ],
                                ),
                                bgcolor=self.colors["accent_orange"],
                            ),
                            height=3,
                            expand=False,
                        ),
                    ],
                    spacing=0,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

        super().__init__(
            content=content,
            padding=ft.padding.only(top=16, left=24, right=24, bottom=0),
            bgcolor=self.colors["bg_primary"],
        )

    def apply_theme(self):
        """Apply current theme to all components."""
        self.colors = self.theme_manager.get_colors()

        self.page_bgcolor = self.colors["bg_primary"]
        self.bgcolor = self.colors["bg_primary"]

        self.logo_container.content.controls[0].bgcolor = self.colors["accent_orange"] + "15"
        self.logo_container.content.controls[0].content.color = self.colors["accent_orange"]
        self.logo_container.content.controls[2].controls[0].color = self.colors["text_primary"]

        self.theme_dropdown.color = self.colors["text_primary"]
        self.theme_dropdown.label_style = ft.TextStyle(color=self.colors["text_secondary"])
        self.theme_dropdown.hint_style = ft.TextStyle(color=self.colors["text_muted"])


# ==========================================================
# Configuration Panel
# ==========================================================

class ConfigPanel(ft.Column):
    """Left panel for configuration inputs."""

    def __init__(self, on_mode_change=None, on_path_update=None):
        self.mode_dropdown = ModeDropdown(on_change=on_mode_change)
        self.url_field = UrlField()
        self.max_pages_field = MaxPagesField()
        self.output_path_field = PathField("Collect 輸出檔案路徑", "cache/listings.jbl")
        self.result_path_field = PathField("Fetch 結果檔案路徑", "cache/results.csv")
        self.quiet_checkbox = QuietCheckbox()

        # Row for max pages + output path
        path_row = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=self.max_pages_field,
                        padding=ft.padding.only(left=20, right=6, bottom=12),
                    ),
                    ft.Container(width=12),
                    ft.Container(
                        content=self.output_path_field,
                        expand=True,
                    ),
                ],
                spacing=0,
            ),
            padding=ft.padding.only(top=0),
        )

        content = ft.Column(
            [
                # Section header
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.TUNE, size=16, color=None),
                            ft.Container(width=8),
                            ft.Text("設定", size=13, weight=ft.FontWeight.W_600, color=None),
                            ft.Container(width=8),
                            ft.IconButton(
                                icon=ft.Icons.INFO_OUTLINED,
                                icon_size=14,
                                icon_color=None,
                                tooltip="設定說明",
                            ),
                        ],
                        spacing=0,
                    ),
                    padding=ft.padding.only(left=20, right=20, top=20, bottom=8),
                ),
                # Form fields
                ft.Container(
                    content=ft.Column(
                        [
                            self.mode_dropdown,
                            self.url_field,
                            path_row,
                            # Fetch result path with quiet checkbox below it
                            ft.Column(
                                [
                                    self.result_path_field,
                                    self.quiet_checkbox,
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=0,
                        tight=True,
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

        # Store reference for external access
        self._content = content

        super().__init__(
            controls=[content],
            spacing=0,
            expand=True,
        )

    def apply_theme(self, colors):
        """Apply current theme to all components."""
        # Section header
        header_container = self.content.controls[0]
        header_content = header_container.content
        header_content.controls[0].color = colors["text_secondary"]
        header_content.controls[2].color = colors["text_secondary"]
        header_content.controls[4].icon_color = colors["text_muted"]

        self.mode_dropdown.apply_theme(colors)
        self.url_field.apply_theme(colors)
        self.max_pages_field.apply_theme(colors)
        self.output_path_field.apply_theme(colors)
        self.result_path_field.apply_theme(colors)
        self.quiet_checkbox.apply_theme(colors)

    def update_paths_for_mode(self, mode: str):
        """Update output paths when mode changes."""
        if mode in MODES:
            config = MODES[mode]
            self.url_field.hint_text = config["url_placeholder"]
            self.output_path_field.value = config["output_path"]
            self.result_path_field.value = config["result_path"]

    def get_config(self) -> Dict:
        """Get current configuration as a dictionary."""
        mode = self.mode_dropdown.value
        config = MODES[mode].copy()
        config["mode"] = mode
        config["url"] = self.url_field.value
        try:
            config["max_pages"] = int(self.max_pages_field.value or "10")
        except ValueError:
            config["max_pages"] = 10
        config["output_path"] = self.output_path_field.value
        config["result_path"] = self.result_path_field.value
        config["quiet"] = self.quiet_checkbox.value
        return config

    @property
    def content(self):
        """Return the internal column content for external access."""
        return self._content


# ==========================================================
# Execution Panel
# ==========================================================

class ExecutionPanel(ft.Column):
    """Right panel for execution control and log display."""

    def __init__(self, log_console_manager, on_start=None, on_stop=None, on_open_result=None):
        self.status_indicator = StatusIndicator()
        self.action_buttons = ActionButtons(
            on_start=on_start,
            on_stop=on_stop,
            on_open_result=on_open_result,
        )

        content = ft.Column(
            [
                # Section header
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.TERMINAL, size=16, color=None),
                            ft.Container(width=8),
                            ft.Text("執行控制台", size=13, weight=ft.FontWeight.W_600, color=None),
                        ],
                        spacing=0,
                    ),
                    padding=ft.padding.only(left=20, right=20, top=20, bottom=8),
                ),
                # Status and buttons
                self.status_indicator,
                self.action_buttons,
                # Log console
                self._create_log_console(log_console_manager),
            ],
            spacing=0,
            expand=True,
        )

        # Store reference for external access
        self._content = content

        super().__init__(
            controls=[content],
            spacing=0,
            expand=True,
        )

    def _create_log_console(self, log_console_manager: LogConsoleManager) -> ft.Container:
        """Create the log console component."""
        return ft.Container(
            content=ft.Column(
                [
                    # Terminal header bar
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(width=12),
                                ft.Container(
                                    content=ft.Icon(ft.Icons.DESKTOP_WINDOWS, size=12, color=None),
                                ),
                                ft.Container(width=8),
                                ft.Text(
                                    "執行日誌",
                                    size=11,
                                    color=None,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.CLEANING_SERVICES,
                                    icon_size=14,
                                    icon_color=None,
                                    tooltip="清除日誌",
                                    on_click=lambda _: log_console_manager.clear_logs(),
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(left=12, right=12, top=8, bottom=8),
                        bgcolor=None,
                        border_radius=ft.border_radius.only(top_left=4, top_right=4),
                    ),
                    # Log content
                    ft.Container(
                        content=log_console_manager.log_console,
                        expand=True,
                    ),
                ],
                spacing=0,
                expand=True,
            ),
            border=ft.border.all(1, None),
            border_radius=4,
            padding=ft.padding.only(top=0),
            bgcolor=None,
            expand=True,
        )

    def apply_theme(self, colors):
        """Apply current theme to all components."""
        # Section header
        header_container = self.content.controls[0]
        header_content = header_container.content
        header_content.controls[0].color = colors["text_secondary"]
        header_content.controls[2].color = colors["text_secondary"]

        self.status_indicator.apply_theme(colors)
        self.action_buttons.apply_theme(colors)

        # Log console
        log_container = self.content.controls[3]
        log_header = log_container.content.controls[0]
        log_header.bgcolor = colors["bg_surface"]
        log_header.content.controls[1].content.color = colors["text_muted"]
        log_header.content.controls[3].color = colors["text_muted"]
        log_header.content.controls[5].icon_color = colors["text_muted"]

        log_container.border = ft.border.all(1, colors["border_subtle"])
        log_container.bgcolor = colors["bg_log"]

    @property
    def content(self):
        """Return the internal column content for external access."""
        return self._content


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

        content = ft.Column(
            [
                header,
                ft.Row(
                    [
                        # Left panel - Configuration (fixed width)
                        ft.Container(
                            content=config_panel.content,
                            width=380,
                            border=ft.border.only(right=ft.border.BorderSide(1, None)),
                            bgcolor=None,
                        ),
                        # Right panel - Execution (flexible)
                        ft.Container(
                            content=execution_panel.content,
                            expand=True,
                        ),
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )

        super().__init__(
            content=content,
            expand=True,
            spacing=0,
        )

        self._header = header
        self._config_panel = config_panel
        self._execution_panel = execution_panel

    def apply_theme(self, colors):
        """Apply current theme to all components."""
        self._header.apply_theme()
        self._config_panel.apply_theme(colors)
        self._execution_panel.apply_theme(colors)

        # Update split panel borders
        left_panel = self.content.controls[1].content.controls[0]
        left_panel.bgcolor = colors["bg_primary"]
        left_panel.border = ft.border.only(right=ft.border.BorderSide(1, colors["border_subtle"]))
