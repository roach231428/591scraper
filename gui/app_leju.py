"""Flet-based GUI for leju.com.tw (樂居) scraper.

This application follows the same pattern as ``gui/app.py`` but is
dedicated to the leju.com.tw sale (中古屋) workflow:

- No mode selection dropdown (中古/新建/租屋 tabs are not needed)
- Visual design follows the leju.com.tw brand palette:
  deep teal (#0F4C5C) header/accent + yellow (#F5B700) call-to-action

The app allows users to:
- Configure URL, max pages, output path
- Run collect and fetch workflows
- Monitor progress in real-time

Module Structure:
    config.py        - Mode configuration and design tokens
    logger.py        - Queue-based logging infrastructure
    scraper_engine.py - Script execution engine
    ui_components.py - Reusable UI components
    main_layout.py   - Main layout components
"""

import os
import sys
from pathlib import Path

import flet as ft

from gui.config import (
    ThemeManager,
    THEMES_LEJU,
    ACCENT_TEAL,
    ACCENT_YELLOW,
    ACCENT_RED,
)
from gui.logger import setup_logger, LogConsoleManager
from gui.scraper_engine import ScraperEngine
from gui.ui_components import (
    UrlField,
    MaxPagesField,
    PathField,
    StatusIndicator,
    NotificationHelper,
)
from gui.main_layout import ExecutionPanel


# ==========================================================
# Leju fixed configuration (no mode dropdown)
# ==========================================================

LEJU_COLLECT_SCRIPT = "collect_leju_list.py"
LEJU_FETCH_SCRIPT = "fetch_leju_info.py"
LEJU_URL_PLACEHOLDER = "https://www.leju.com.tw/object_list?..."
LEJU_RESULT_PATH = "cache/leju_results.csv"


def get_base_path() -> Path:
    """Get the base directory of the application.

    For PyInstaller bundled apps, sys._MEIPASS points to the temp directory
    where the app is extracted. We want to use the current working directory
    instead so that relative paths (like cache/) work correctly.

    Returns the project root directory (parent of gui/).
    """
    if getattr(sys, "frozen", False):
        return Path.cwd()
    else:
        return Path(__file__).parent.parent  # Go up from gui/ to project root


# ==========================================================
# Leju-themed UI components
# ==========================================================

class LejuHeader(ft.Container):
    """Application header with leju branding and theme selector."""

    def __init__(self, theme_manager, on_theme_change=None):
        self.theme_manager = theme_manager
        self.colors = theme_manager.get_colors()

        self.logo_icon = ft.Icon(
            ft.Icons.HOME,
            size=20,
            color=ACCENT_YELLOW,
        )

        self.logo_icon_container = ft.Container(
            content=self.logo_icon,
            padding=6,
            bgcolor=ACCENT_YELLOW + "25",
            border_radius=4,
        )

        self.logo_title = ft.Text(
            "樂居 房產爬蟲工具",
            size=16,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.WHITE,
        )

        self.logo_subtitle = ft.Text(
            "leju.com.tw 實價登錄 · 中古屋",
            size=11,
            color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
        )

        self.theme_dropdown = self._build_theme_dropdown(on_theme_change)

        self.logo_container = self._build_logo()
        content = self._build_content()

        super().__init__(
            content=content,
            padding=ft.Padding.only(top=14, left=24, right=24, bottom=0),
            bgcolor=ACCENT_TEAL,
        )

    def _build_theme_dropdown(self, on_theme_change=None) -> ft.Dropdown:
        """Create the theme selector (styled for the dark teal header)."""
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
            color=ft.Colors.WHITE,
            label_style=ft.TextStyle(color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
            hint_style=ft.TextStyle(color=ft.Colors.with_opacity(0.6, ft.Colors.WHITE)),
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
                            self.logo_subtitle,
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

    def _build_content(self) -> ft.Column:
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
            spacing=10,
            tight=True,
            expand=True,
        )

    def _build_accent_line(self) -> ft.Container:
        """Create the yellow accent line (leju CTA color)."""
        return ft.Container(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Container(expand=1),
                        ft.Container(
                            content=ft.Text(
                                "LEJU",
                                size=8,
                                color=ACCENT_TEAL,
                                weight=ft.FontWeight.W_700,
                            ),
                            padding=ft.Padding.only(left=4, right=4, top=1, bottom=1),
                        ),
                        ft.Container(expand=3),
                    ],
                ),
                bgcolor=ACCENT_YELLOW,
            ),
            height=3,
            expand=False,
        )

    def apply_theme(self, colors):
        """Apply the given theme colors.

        The header keeps the fixed leju teal branding; only the theme
        dropdown text colors follow the selected theme.
        """
        self.colors = colors
        self.bgcolor = ACCENT_TEAL


class LejuConfigPanel(ft.Column):
    """Left panel containing leju scraper configuration.

    Same as ``ConfigPanel`` in main_layout.py but without the mode
    selection dropdown (leju only scrapes 中古屋 sale listings).
    """

    DEFAULT_MAX_PAGES = 10

    def __init__(self):
        self._on_page_count_change = None
        self.url_field = UrlField()
        self.max_pages_field = MaxPagesField(on_change=self._notify_page_count_change)
        self.result_path_field = PathField(
            "Fetch 結果檔案路徑",
            LEJU_RESULT_PATH,
        )

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

        # Apply the leju URL placeholder hint
        self.url_field.hint_text = LEJU_URL_PLACEHOLDER

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
            padding=ft.Padding.only(left=20, right=20, top=20, bottom=8),
        )

    def _build_form(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    self.url_field,
                    self._build_max_pages_row(),
                    self._build_result_section(),
                ],
                spacing=0,
                tight=True,
                expand=True,
            ),
            expand=True,
        )

    def _build_max_pages_row(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=self.max_pages_field,
                        padding=ft.Padding.only(left=20, right=6, bottom=12),
                    ),
                ],
                spacing=0,
            ),
        )

    def _build_result_section(self) -> ft.Column:
        return ft.Column(
            [
                self.result_path_field,
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
            self.url_field,
            self.max_pages_field,
            self.result_path_field,
        ):
            field.apply_theme(colors)

    # ------------------------------------------------------
    # Configuration
    # ------------------------------------------------------

    def get_config(self) -> dict:
        return dict(
            url=self.url_field.value,
            max_pages=self._get_max_pages(),
            result_path=self.result_path_field.value,
        )

    def _get_max_pages(self) -> int:
        try:
            return int(self.max_pages_field.value or self.DEFAULT_MAX_PAGES)
        except (TypeError, ValueError):
            return self.DEFAULT_MAX_PAGES

    def set_page_count_change_callback(self, callback):
        """Register a callback invoked when the stepper buttons change the value."""
        self._on_page_count_change = callback

    def _notify_page_count_change(self):
        """Notify the app so it can refresh the UI after a stepper click."""
        if self._on_page_count_change:
            self._on_page_count_change()


class LejuActionButtons(ft.Row):
    """Action buttons row styled with the leju brand palette.

    Start button uses the leju yellow CTA color (with dark teal text,
    like the 找房 button on leju.com.tw); stop keeps the error red.
    """

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
            bgcolor=ACCENT_YELLOW,
            color=ACCENT_TEAL,
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


class LejuStatusIndicator(StatusIndicator):
    """Status indicator re-colored with the leju brand palette."""

    def __init__(self):
        super().__init__()
        self.loading_spinner.color = ACCENT_TEAL
        self.progress_bar.color = ACCENT_TEAL


class LejuExecutionPanel(ExecutionPanel):
    """Execution panel re-skinned with leju brand components.

    Reuses the layout/log-console logic of ``ExecutionPanel`` but swaps
    the status indicator and action buttons for leju-colored versions.
    """

    def __init__(
        self,
        log_console_manager,
        on_start=None,
        on_stop=None,
        on_open_result=None,
    ):
        super().__init__(
            log_console_manager=log_console_manager,
            on_start=on_start,
            on_stop=on_stop,
            on_open_result=on_open_result,
        )

        # Swap in leju-themed controls (same object names so the rest of
        # ExecutionPanel / app code keeps working unchanged).
        self.status_indicator = LejuStatusIndicator()
        self.action_buttons = LejuActionButtons(
            on_start=on_start,
            on_stop=on_stop,
            on_open_result=on_open_result,
        )

        # Rebuild the content column so the new controls take effect.
        self._content = self._build_content()
        self.controls = [self._content]

    def apply_theme(self, colors):
        """Apply theme colors, then re-assert the leju accent colors."""
        super().apply_theme(colors)
        self.status_indicator.loading_spinner.color = ACCENT_TEAL
        self.status_indicator.progress_bar.color = ACCENT_TEAL


class LejuMainLayout(ft.Column):
    """Main application layout with leju header and split panels."""

    def __init__(
        self,
        theme_manager,
        config_panel,
        execution_panel,
        on_theme_change=None,
    ):
        header = LejuHeader(theme_manager, on_theme_change=on_theme_change)

        self._left_panel = ft.Container(
            content=config_panel,
            width=380,
            border=ft.Border.only(right=ft.border.BorderSide(1, None)),
            bgcolor=None,
        )
        self.right_panel = ft.Container(
            content=execution_panel,
            expand=True,
            padding=ft.Padding(left=10, right=10),
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
            spacing=10,
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
        self._left_panel.border = ft.Border.only(
            right=ft.border.BorderSide(1, colors["border_subtle"])
        )


# ==========================================================
# Application controller
# ==========================================================

class LejuScraperApp:
    """Main application controller for the leju scraper GUI."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.is_running = {"value": False}
        self.fetch_progress = {"idx": 0, "total": 0}

        # Initialize components
        self._init_theme()
        self._init_logger()
        self._init_scraper_engine()
        self._init_ui()
        self._setup_page()

    def _init_theme(self):
        """Initialize theme manager with the leju palette."""
        self.theme_manager = ThemeManager(
            self.page,
            initial_theme="system",
            themes=THEMES_LEJU,
        )

    def _init_logger(self):
        """Initialize logging infrastructure."""
        self.logger = setup_logger()
        self.log_console = LogConsoleManager(
            self.page,
            get_colors=lambda: self.theme_manager.get_colors()
        )

    def _init_scraper_engine(self):
        """Initialize scraper engine with callbacks."""
        self.scraper_engine = ScraperEngine(
            on_progress=self._on_progress,
            on_log=self._on_log
        )

    def _init_ui(self):
        """Initialize UI components."""
        # Notification helper
        self.notification_helper = NotificationHelper(self.page)

        # Config panel (no mode dropdown)
        self.config_panel = LejuConfigPanel()
        self.config_panel.set_page_count_change_callback(self._on_page_count_change)

        # Execution panel (leju-styled)
        self.execution_panel = LejuExecutionPanel(
            log_console_manager=self.log_console,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_open_result=self._on_open_result
        )

        # Main layout - combines header, config panel, and execution panel
        self.main_layout = LejuMainLayout(
            theme_manager=self.theme_manager,
            config_panel=self.config_panel,
            execution_panel=self.execution_panel,
            on_theme_change=self._on_theme_change,
        )

    def _setup_page(self):
        """Configure page properties."""
        self.page.title = "樂居 房產爬蟲工具"
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.padding = ft.Padding.only(top=0, left=0, right=0, bottom=0)
        self.page.theme_mode = self.theme_manager.get_theme_mode()
        self.page.theme = None
        self.page.bgcolor = self.theme_manager.get_colors()["bg_primary"]

        # Add main layout to page
        self.page.add(self.main_layout)

        # Start log flushing
        self.log_console.start_flush_loop()

    # ==========================================================
    # Background Worker - runs in background thread
    # ==========================================================

    def _create_worker(self, config: dict):
        """Create a background worker function for running the scraper.

        Args:
            config: Configuration dictionary with scraper settings.

        Returns:
            A worker function suitable for page.run_thread().
        """
        def worker():
            try:
                app_dir = get_base_path()

                # Use absolute path if user provided one, otherwise resolve relative to app_dir
                result_path = config["result_path"]
                abs_result_path = str(Path(result_path).resolve() if Path(result_path).is_absolute() else app_dir / result_path)

                self._log("開始執行 - 模式: 樂居中古屋")
                self._log(f"URL: {config['url']}")
                self._log(f"最大頁數: {config['max_pages']}")
                self._log(f"結果路徑: {abs_result_path}")

                # Ensure cache directory exists
                Path(abs_result_path).parent.mkdir(parents=True, exist_ok=True)

                # Run collect phase
                self._update_status("正在執行 Collect...", 0.0)
                self._log("=== Collect 階段 ===")

                collect_result = self.scraper_engine.run_collect(
                    script_name=LEJU_COLLECT_SCRIPT,
                    url=config["url"],
                    max_pages=config["max_pages"],
                    quiet=False,
                )

                if not collect_result.success:
                    self._log(f"Collect 失敗: {collect_result.error}")
                    self._update_status("Collect 失敗", 1.0)

                    def show_collect_error():
                        self.execution_panel.action_buttons.start_button.disabled = False
                        self.execution_panel.action_buttons.stop_button.disabled = True
                        self.page.update()

                    self.page.run_thread(show_collect_error)
                    return

                id_list = collect_result.id_list or []
                self._log(f"Collect 完成 - 收集到 {len(id_list)} 筆資料")

                # Run fetch phase with the collected IDs passed directly
                self._update_status("正在執行 Fetch...", 0.5)
                self._log("=== Fetch 階段 ===")
                self.page.run_thread(lambda: self.page.update())

                fetch_result = self.scraper_engine.run_fetch(
                    script_name=LEJU_FETCH_SCRIPT,
                    output_path=abs_result_path,
                    id_list=id_list,
                    quiet=False,
                )

                if not fetch_result.success:
                    self._log(f"Fetch 失敗: {fetch_result.error}")
                    self._update_status("Fetch 失敗", 1.0)

                    def show_fetch_error():
                        self.execution_panel.action_buttons.start_button.disabled = False
                        self.execution_panel.action_buttons.stop_button.disabled = True
                        self.page.update()

                    self.page.run_thread(show_fetch_error)
                    return

                self._log("Fetch 完成!")
                self._update_status("執行完成", 1.0)

                # Show success notification on main thread
                def show_success_notification():
                    self.notification_helper.show_success(
                        "執行完成",
                        "模式: 樂居中古屋\nCollect 與 Fetch 階段均已成功完成"
                    )
                    # Reset button states on main thread
                    self.execution_panel.action_buttons.start_button.disabled = False
                    self.execution_panel.action_buttons.stop_button.disabled = True
                    self.execution_panel.action_buttons.open_result_button.disabled = False
                    self.page.update()

                self.page.run_thread(show_success_notification)

            except Exception as ex:
                import traceback
                error_details = traceback.format_exc()
                self._log(f"執行錯誤: {error_details}")

                def show_error():
                    self.notification_helper.show_error(
                        "執行錯誤",
                        f"{type(ex).__name__}: {str(ex)}"
                    )
                    self.execution_panel.action_buttons.start_button.disabled = False
                    self.execution_panel.action_buttons.stop_button.disabled = True
                    self.page.update()

                self.page.run_thread(show_error)

        return worker

    # ==========================================================
    # Event Handlers
    # ==========================================================

    def _on_theme_change(self, e):
        """Handle theme dropdown change."""
        self.theme_manager.value = e.control.value
        colors = self.theme_manager.get_colors()

        self.page.bgcolor = colors["bg_primary"]
        self.page.theme_mode = self.theme_manager.get_theme_mode()
        self.main_layout.apply_theme(colors)
        self.log_console.update_log_colors()

        self.page.update()

    def _on_page_count_change(self):
        """Refresh the UI after the max pages stepper changes the value."""
        self.page.update()

    def _on_progress(self, status_text: str, progress: float):
        """Handle progress updates from scraper engine."""
        self.execution_panel.status_indicator.update_status(status_text, progress)

        colors = self.theme_manager.get_colors()
        self.execution_panel.status_indicator.status_text.color = colors["status_running"]

        self.page.run_thread(lambda: self.page.update())

    def _on_log(self, message: str):
        """Handle log messages from scraper engine."""
        self.logger.info(message)

    def _on_start(self, e):
        """Handle start button click."""
        config = self.config_panel.get_config()

        if not config["url"]:
            self.notification_helper.show_warning_dialog("警告", [
                ft.Text("請輸入 URL"),
            ])
            return

        # Reset UI state
        self.log_console.clear_logs()
        self.execution_panel.action_buttons.start_button.disabled = True
        self.execution_panel.action_buttons.stop_button.disabled = False
        self.execution_panel.action_buttons.open_result_button.disabled = True
        self.is_running["value"] = True

        # Create and run worker in background thread
        worker = self._create_worker(config)
        self.page.run_thread(worker)

    def _on_stop(self, e):
        """Handle stop button click."""
        self.is_running["value"] = False
        self._log("使用者要求停止...")

    def _on_open_result(self, e):
        """Handle open result button click."""
        config = self.config_panel.get_config()
        result_path = config["result_path"]

        # Use absolute path if user provided one, otherwise resolve relative to app_dir
        app_dir = get_base_path()
        result_file = Path(result_path).resolve() if Path(result_path).is_absolute() else app_dir / result_path

        self._log(f"嘗試開啟檔案: {result_file} (存在: {result_file.exists()})")

        if result_file.exists():
            try:
                os.startfile(str(result_file))
                self._log("開啟結果檔案成功")
            except Exception as ex:
                self.notification_helper.show_warning_dialog("錯誤", [
                    ft.Text(f"開啟檔案失敗: {str(ex)}"),
                ])
        else:
            cache_dir = app_dir / "cache"
            cache_files = [
                f.name for f in cache_dir.iterdir()
            ] if cache_dir.exists() else []
            self.notification_helper.show_warning_dialog("警告", [
                ft.Text(f"找不到結果檔案: {result_file}"),
                ft.Text(f"cache 目錄內容: {', '.join(cache_files)}"),
            ])

    # ==========================================================
    # Helper Methods
    # ==========================================================

    def _log(self, message: str):
        """Log a message."""
        self.logger.info(message)

    def _update_status(self, status: str, progress: float = None):
        """Update status display."""
        colors = self.theme_manager.get_colors()
        self.execution_panel.status_indicator.update_status(status, progress)

        if "失敗" in status:
            self.execution_panel.status_indicator.status_text.color = colors["status_error"]
        elif "完成" in status:
            self.execution_panel.status_indicator.status_text.color = colors["status_complete"]
        elif self.is_running["value"]:
            self.execution_panel.status_indicator.status_text.color = colors["status_running"]
        else:
            self.execution_panel.status_indicator.status_text.color = colors["status_idle"]

        self.page.run_thread(lambda: self.page.update())

    def _reset_buttons(self):
        """Reset button states after execution."""
        def reset():
            self.is_running["value"] = False
            self.execution_panel.action_buttons.start_button.disabled = False
            self.execution_panel.action_buttons.stop_button.disabled = True
            self.page.update()

        self.page.run_thread(reset)


def app(page: ft.Page):
    """Main application entry point.

    Args:
        page: Flet page instance.
    """
    # Ensure cache directory exists
    Path("cache").mkdir(exist_ok=True)

    # Initialize and store app instance
    LejuScraperApp(page)


# ==========================================================
# Entry
# ==========================================================
if __name__ == "__main__":
    ft.run(app)
