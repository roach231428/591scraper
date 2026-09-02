"""UI components for the 591 scraper GUI application.

This module provides reusable UI components:
- Theme-aware dropdown and text fields
- Status indicator with progress ring
- Action buttons (start, stop, open result)
- Notification dialogs
"""

import flet as ft
from typing import Optional

from gui.config import ACCENT_ORANGE, ACCENT_RED, SUCCESS_GREEN, MODES


# ==========================================================
# Theme-Aware Input Components
# ==========================================================

class ModeDropdown(ft.Container):
    """Mode selection dropdown."""

    def __init__(self, on_select=None):
        self.dropdown = ft.Dropdown(
            label="模式選擇",
            options=[ft.dropdown.Option(k) for k in MODES.keys()],
            value="租屋",
            expand=True,
            color=None,  # Will be set by apply_theme
            label_style=None,
            hint_style=None,
        )
        super().__init__(
            content=self.dropdown,
            padding=ft.Padding.only(left=20, right=20, bottom=12),
        )
        self.dropdown.on_select = on_select

    @property
    def value(self):
        return self.dropdown.value

    def apply_theme(self, colors):
        self.dropdown.color = colors["text_primary"]
        self.dropdown.label_style = ft.TextStyle(color=colors["text_secondary"])
        self.dropdown.hint_style = ft.TextStyle(color=colors["text_muted"])


class UrlField(ft.Container):
    """URL input field."""

    def __init__(self):
        self.field = ft.TextField(
            label="列表頁面 URL",
            hint_text="輸入 591 列表頁面 URL",
            expand=True,
            value="",
            filled=True,
            bgcolor=None,
            border_color=None,
            focused_border_color=None,
            color=None,
            label_style=None,
            hint_style=None,
        )
        super().__init__(
            content=self.field,
            padding=ft.Padding.only(left=20, right=20, bottom=12),
        )

    @property
    def value(self):
        return self.field.value

    @property
    def hint_text(self):
        return self.field.hint_text

    @hint_text.setter
    def hint_text(self, value):
        self.field.hint_text = value

    def apply_theme(self, colors):
        self.field.bgcolor = colors["bg_input"]
        self.field.border_color = colors["border_subtle"]
        self.field.focused_border_color = colors["border_focus"]
        self.field.color = colors["text_primary"]
        self.field.label_style = ft.TextStyle(color=colors["text_secondary"])
        self.field.hint_style = ft.TextStyle(color=colors["text_muted"])


class MaxPagesField(ft.Container):
    """Max pages input field."""

    def __init__(self):
        self.field = ft.TextField(
            label="最大頁數",
            value="10",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            filled=True,
            bgcolor=None,
            border_color=None,
            focused_border_color=None,
            color=None,
            label_style=None,
            hint_style=None,
        )
        super().__init__(
            content=self.field,
            expand=False,
        )

    @property
    def value(self):
        return self.field.value

    def apply_theme(self, colors):
        self.field.bgcolor = colors["bg_input"]
        self.field.border_color = colors["border_subtle"]
        self.field.focused_border_color = colors["border_focus"]
        self.field.color = colors["text_primary"]
        self.field.label_style = ft.TextStyle(color=colors["text_secondary"])
        self.field.hint_style = ft.TextStyle(color=colors["text_muted"])


class PathField(ft.Container):
    """Path input field."""

    def __init__(self, label: str, value: str):
        self.field = ft.TextField(
            label=label,
            value=value,
            expand=True,
            filled=True,
            bgcolor=None,
            border_color=None,
            focused_border_color=None,
            color=None,
            label_style=None,
            hint_style=None,
        )
        super().__init__(
            content=self.field,
            padding=ft.Padding.only(left=20, right=20, bottom=12),
            expand=True,
        )

    @property
    def value(self):
        return self.field.value

    @value.setter
    def value(self, new_value):
        self.field.value = new_value

    def apply_theme(self, colors):
        self.field.bgcolor = colors["bg_input"]
        self.field.border_color = colors["border_subtle"]
        self.field.focused_border_color = colors["border_focus"]
        self.field.color = colors["text_primary"]
        self.field.label_style = ft.TextStyle(color=colors["text_secondary"])
        self.field.hint_style = ft.TextStyle(color=colors["text_muted"])


class QuietCheckbox(ft.Container):
    """Quiet mode checkbox."""

    def __init__(self):
        self.checkbox = ft.Checkbox(
            label="靜默模式 (不開啟瀏覽器)",
            value=False,
            active_color=ACCENT_ORANGE,
            label_style=None,
        )
        super().__init__(
            content=self.checkbox,
            padding=ft.Padding.only(left=20, right=20, bottom=20),
        )

    @property
    def value(self):
        return self.checkbox.value

    def apply_theme(self, colors):
        self.checkbox.label_style = ft.TextStyle(color=colors["text_secondary"])


# ==========================================================
# Status Components
# ==========================================================

class StatusIndicator(ft.Container):
    """Status indicator with progress ring and progress bar."""

    def __init__(self):
        self.status_text = ft.Text(
            value="準備就緒",
            size=14,
            color=None,
        )
        self.phase_label = ft.Text(
            value="",
            size=12,
            color=None,
            weight=ft.FontWeight.W_500,
        )
        self.loading_spinner = ft.ProgressRing(
            stroke_width=2,
            width=16,
            height=16,
            color=ACCENT_ORANGE,
            visible=False,
        )
        self.progress_bar = ft.ProgressBar(
            expand=True,
            color=ACCENT_ORANGE,
            bgcolor=None,
            visible=False,
        )

        content = ft.Column(
            [
                ft.Row(
                    [
                        self.loading_spinner,
                        ft.Container(width=8),
                        self.status_text,
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.phase_label,
                self.progress_bar,
                ft.Container(height=16),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=content,
            padding=ft.Padding.only(left=20, right=20, bottom=12),
        )

    def update_status(self, status: str, progress: Optional[float] = None):
        """Update status text and progress.

        Args:
            status: Status text to display.
            progress: Progress value (0.0 to 1.0), or None to hide progress bar.
        """
        if "失敗" in status:
            self.status_text.value = status
            self.phase_label.value = ""
            self.loading_spinner.visible = False
        elif "完成" in status:
            self.status_text.value = status
            self.phase_label.value = ""
            self.loading_spinner.visible = False
        else:
            self.status_text.value = status
            self.loading_spinner.visible = True
            if "Collect" in status:
                self.phase_label.value = "● Collect 階段"
            elif "Fetch" in status:
                self.phase_label.value = "● Fetch 階段"
            else:
                self.phase_label.value = ""

        if progress is not None:
            self.progress_bar.visible = True
            self.progress_bar.value = progress

    def apply_theme(self, colors):
        self.status_text.color = colors["status_idle"]
        self.phase_label.color = colors["text_secondary"]
        self.progress_bar.bgcolor = colors["border_subtle"]


# ==========================================================
# Action Buttons
# ==========================================================

class ActionButtons(ft.Row):
    """Action buttons row (Start, Stop, Open Result)."""

    def __init__(self, on_start=None, on_stop=None, on_open_result=None):
        self.start_button = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PLAY_ARROW, size=18),
                    ft.Container(width=8),
                    ft.Text("開始執行"),
                ],
                spacing=0,
            ),
            bgcolor=ACCENT_ORANGE,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shadow_color=ft.Colors.TRANSPARENT,
                padding=ft.Padding.only(left=24, right=24, top=12, bottom=12),
                shape=ft.RoundedRectangleBorder(radius=4),
            ),
        )
        self.stop_button = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.STOP, size=18),
                    ft.Container(width=8),
                    ft.Text("停止"),
                ],
                spacing=0,
            ),
            disabled=True,
            bgcolor=ACCENT_RED,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shadow_color=ft.Colors.TRANSPARENT,
                padding=ft.Padding.only(left=24, right=24, top=12, bottom=12),
                shape=ft.RoundedRectangleBorder(radius=4),
            ),
        )
        self.open_result_button = ft.TextButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=18),
                    ft.Container(width=8),
                    ft.Text("開啟結果檔案"),
                ],
                spacing=0,
            ),
            disabled=True,
            style=ft.ButtonStyle(
                padding=ft.Padding.only(left=16, right=16, top=12, bottom=12),
                color=None,
            ),
        )

        super().__init__(
            [
                self.start_button,
                ft.Container(width=12),
                self.stop_button,
                ft.Container(width=12),
                self.open_result_button,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0,
        )

        self.start_button.on_click = on_start
        self.stop_button.on_click = on_stop
        self.open_result_button.on_click = on_open_result

    def apply_theme(self, colors):
        self.open_result_button.style.color = colors["text_secondary"]


# ==========================================================
# Notification Dialogs
# ==========================================================

class NotificationHelper:
    """Helper for showing notification dialogs."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._current_dialog = None

    def _show_dialog(self, title: str, message: str, icon: ft.Icons, color: str):
        """Show a notification dialog."""
        def close_dialog(e):
            self.page.pop_dialog()

        self._current_dialog = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(icon, size=24, color=color),
                    ft.Container(width=8),
                    ft.Text(title, weight=ft.FontWeight.W_600),
                ],
                spacing=0,
            ),
            content=ft.Text(message, style=ft.TextStyle(size=14)),
            actions=[
                ft.TextButton("確定", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self._current_dialog)

    def show_success(self, title: str, message: str):
        """Show success notification."""
        self._show_dialog(title, message, ft.Icons.CHECK_CIRCLE, SUCCESS_GREEN)

    def show_error(self, title: str, message: str):
        """Show error notification."""
        self._show_dialog(title, message, ft.Icons.ERROR, ACCENT_RED)

    def show_warning(self, title: str, message: str):
        """Show warning notification."""
        self._show_dialog(title, message, ft.Icons.WARNING, ACCENT_ORANGE)

    def show_warning_dialog(self, title: str, content_controls):
        """Show a warning dialog with custom content.

        Args:
            title: Dialog title.
            content_controls: List of Flet controls to display as content.
        """
        def close_dialog(e):
            self.page.pop_dialog()

        self._current_dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(content_controls, tight=True),
            actions=[
                ft.TextButton("確定", on_click=close_dialog),
            ],
        )
        self.page.show_dialog(self._current_dialog)
