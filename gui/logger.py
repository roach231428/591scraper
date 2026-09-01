"""Logging infrastructure for the 591 scraper GUI application.

This module provides:
- Queue-based log handler for thread-safe logging
- Log flush loop for real-time UI updates
- Log management utilities
"""

import logging
from queue import Queue

import flet as ft


# ==========================================================
# Global Log Queue
# ==========================================================

log_queue: Queue = Queue()


# ==========================================================
# Queue Handler
# ==========================================================

class QueueHandler(logging.Handler):
    """Custom logging handler that pushes log records to a queue."""

    def emit(self, record):
        self.format(record)  # Apply formatting
        log_queue.put(self.formatted_record if hasattr(self, 'formatted_record') else record.msg)


# ==========================================================
# Logger Setup
# ==========================================================

def setup_logger() -> logging.Logger:
    """Configure and return the application logger.

    Sets up a QueueHandler to capture all log output for UI display.

    Returns:
        Configured logger instance.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    queue_handler = QueueHandler()
    queue_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(queue_handler)

    return logging.getLogger("scraper")


# ==========================================================
# Log Console Manager
# ==========================================================

class LogConsoleManager:
    """Manages the log console UI component and log flushing loop."""

    def __init__(self, page: ft.Page, get_colors):
        """Initialize the log console manager.

        Args:
            page: Flet page instance.
            get_colors: Callback function that returns color tokens dict.
        """
        self.page = page
        self.get_colors = get_colors
        self.log_console = ft.ListView(
            expand=True,
            spacing=0,
            auto_scroll=True,
        )
        self._flush_task = None

    def clear_logs(self):
        """Clear all log entries from the console."""
        self.log_console.controls.clear()
        self.page.update()

    def update_log_colors(self):
        """Update log text colors when theme changes."""
        colors = self.get_colors()
        for control in self.log_console.controls:
            if isinstance(control, ft.Text):
                control.color = colors["text_primary"]
        self.page.update()

    def start_flush_loop(self):
        """Start the asynchronous log flush loop."""
        import asyncio

        async def flush_logs():
            while True:
                updated = False
                while not log_queue.empty():
                    msg = log_queue.get()
                    self.log_console.controls.append(
                        ft.Text(
                            msg,
                            style=ft.TextStyle(
                                font_family="Consolas",
                                size=13,
                                color=self.get_colors()["text_primary"]
                            )
                        )
                    )
                    updated = True
                if updated:
                    try:
                        self.page.update()
                    except Exception:
                        logger = logging.getLogger("scraper")
                        logger.exception("Failed to update log_console")
                await asyncio.sleep(0.2)

        self.page.run_task(flush_logs)
