"""Flet-based GUI for 591.com.tw scraper.

This application provides a graphical interface for running the 591 scraper
collect and fetch workflows. It supports three modes:
- Rent (租屋): Rental listings
- Second-hand (中古屋): Second-hand property listings

The app allows users to:
- Select the scraping mode
- Configure URL, max pages, output path
- Toggle quiet mode (headless browser)
- Run collect and fetch workflows
- Monitor progress in real-time

Module Structure:
    config.py       - Mode configuration and design tokens
    logger.py       - Queue-based logging infrastructure
    scraper_engine.py - Script execution engine
    ui_components.py - Reusable UI components
    main_layout.py  - Main layout components
"""

import os
import sys
from pathlib import Path

import flet as ft

from gui.config import ThemeManager, MODES
from gui.logger import setup_logger, LogConsoleManager
from gui.scraper_engine import ScraperEngine
from gui.ui_components import NotificationHelper
from gui.main_layout import MainLayout, ConfigPanel, ExecutionPanel


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


class ScraperApp:
    """Main application controller for the 591 scraper GUI."""

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
        """Initialize theme manager."""
        self.theme_manager = ThemeManager(
            self.page,
            initial_theme="system",
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

        # Config panel
        self.config_panel = ConfigPanel(
            on_mode_change=self._on_mode_change
        )

        # Execution panel
        self.execution_panel = ExecutionPanel(
            log_console_manager=self.log_console,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_open_result=self._on_open_result
        )

        # Main layout - combines header, config panel, and execution panel
        self.main_layout = MainLayout(
            theme_manager=self.theme_manager,
            config_panel=self.config_panel,
            execution_panel=self.execution_panel,
            on_theme_change=self._on_theme_change,
        )

    def _setup_page(self):
        """Configure page properties."""
        self.page.title = "591 房產爬蟲工具"
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

        This follows the pattern from the example where worker() runs in a background thread
        and uses page.run_thread() to update UI elements.

        Args:
            config: Configuration dictionary with scraper settings.

        Returns:
            A worker function suitable for page.run_thread().
        """
        def worker():
            try:
                self._log(f"開始執行 - 模式: {config['mode']}")
                self._log(f"URL: {config['url']}")
                self._log(f"最大頁數: {config['max_pages']}")
                self._log(f"靜默模式: {'是' if config['quiet'] else '否'}")

                # Run collect phase
                self._update_status("正在執行 Collect...", 0.0)
                self._log("=== Collect 階段 ===")

                mode_config = MODES[config["mode"]]
                collect_result = self.scraper_engine.run_collect(
                    script_name=mode_config["collect_script"],
                    url=config["url"],
                    output_path=config["output_path"],
                    max_pages=config["max_pages"],
                    quiet=config["quiet"],
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

                count = self.scraper_engine.parse_collected_count(collect_result.output)
                self._log(f"Collect 完成 - 收集到 {count} 筆資料")

                # Run fetch phase
                self._update_status("正在執行 Fetch...", 0.5)
                self._log("=== Fetch 階段 ===")
                self.page.run_thread(lambda: self.page.update())

                fetch_result = self.scraper_engine.run_fetch(
                    script_name=mode_config["fetch_script"],
                    source_path=config["output_path"],
                    output_path=config["result_path"],
                    quiet=config["quiet"],
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
                        f"模式: {config['mode']}\nCollect 與 Fetch 階段均已成功完成"
                    )

                self.page.run_thread(show_success_notification)

                # Enable open result button on main thread
                def enable_open_button():
                    self.execution_panel.action_buttons.open_result_button.disabled = False
                    self.page.update()

                self.page.run_thread(enable_open_button)

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

    def _on_mode_change(self, e):
        """Handle mode dropdown change."""
        mode = self.config_panel.mode_dropdown.value
        self.config_panel.update_paths_for_mode(mode)
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

        # Create and run worker in background thread (like the example)
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
        app_dir = get_base_path()
        result_file = app_dir / result_path

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
    ScraperApp(page)


# ==========================================================
# Entry
# ==========================================================
if __name__ == "__main__":
    ft.run(app)
