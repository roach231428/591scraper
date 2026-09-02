"""Scraper engine for executing collect and fetch workflows.

This module provides:
- Direct function call-based script execution
- Real-time progress tracking
- Output capture and parsing
"""

import builtins
import logging
import re

logger = logging.getLogger("scraper")


# ==========================================================
# Script Function Registry
# ==========================================================

# Import scraper main functions (lazy-loaded to avoid circular imports)
def _get_script_functions():
    """Lazy-load scraper main functions."""
    from scraper.collect_sale_list import main as collect_sale_main
    from scraper.collect_newhouse_list import main as collect_newhouse_main
    from scraper.collect_rent_list import main as collect_rent_main
    from scraper.fetch_sale_info import main as fetch_sale_main
    from scraper.fetch_rent_info import main as fetch_rent_main

    return {
        "collect_sale_list.py": collect_sale_main,
        "collect_newhouse_list.py": collect_newhouse_main,
        "collect_rent_list.py": collect_rent_main,
        "fetch_sale_info.py": fetch_sale_main,
        "fetch_rent_info.py": fetch_rent_main,
    }


# ==========================================================
# Progress Tracker
# ==========================================================

class ProgressTracker:
    """Tracks scraper execution progress."""

    def __init__(self):
        self.idx: int = 0
        self.total: int = 0
        self.running: bool = False

    @property
    def percentage(self) -> float:
        """Get progress as a percentage (0.0 to 1.0)."""
        if self.total == 0:
            return 0.0
        return min(self.idx / self.total, 1.0)


# ==========================================================
# Scraper Result
# ==========================================================

class ScraperResult:
    """Represents the result of a scraper execution."""

    def __init__(self, success: bool, output: str = "", error: str = ""):
        self.success = success
        self.output = output
        self.error = error

    @classmethod
    def success_result(cls, output: str = "") -> "ScraperResult":
        return cls(success=True, output=output)

    @classmethod
    def error_result(cls, error: str) -> "ScraperResult":
        return cls(success=False, error=error)


# ==========================================================
# Scraper Engine
# ==========================================================

class ScraperEngine:
    """Executes scraper scripts with progress tracking and output capture."""

    def __init__(self, on_progress=None, on_log=None):
        """Initialize the scraper engine.

        Args:
            on_progress: Callback function(status_text, progress) for progress updates.
            on_log: Callback function(message) for log output.
        """
        self._on_progress = on_progress
        self._on_log = on_log
        self._progress = ProgressTracker()
        self._functions = {}
        self._original_print = None
        self._output_lines = []

    def _ensure_functions_loaded(self):
        """Ensure script functions are loaded."""
        if not self._functions:
            self._functions = _get_script_functions()

    def run_collect(
        self,
        script_name: str,
        url: str,
        output_path: str,
        max_pages: int,
        quiet: bool,
    ) -> ScraperResult:
        """Run a collect phase script.

        Args:
            script_name: Script filename (e.g., "collect_sale_list.py").
            url: 591 listing page URL.
            output_path: Path to save collected listings.
            max_pages: Maximum number of pages to scrape.
            quiet: Whether to run in headless mode.

        Returns:
            ScraperResult with execution outcome.
        """
        self._ensure_functions_loaded()

        func = self._functions.get(script_name)
        if func is None:
            return ScraperResult.error_result(f"未知的腳本: {script_name}")

        return self._run_with_args(
            func,
            url=url,
            output_path=output_path,
            max_pages=max_pages,
            quiet=quiet,
        )

    def run_fetch(
        self,
        script_name: str,
        source_path: str,
        output_path: str,
        quiet: bool,
    ) -> ScraperResult:
        """Run a fetch phase script.

        Args:
            script_name: Script filename (e.g., "fetch_sale_info.py").
            source_path: Path to collected listings file.
            output_path: Path to save fetched results.
            quiet: Whether to run in headless mode.

        Returns:
            ScraperResult with execution outcome.
        """
        self._ensure_functions_loaded()

        func = self._functions.get(script_name)
        if func is None:
            return ScraperResult.error_result(f"未知的腳本: {script_name}")

        return self._run_with_args(
            func,
            source_path=source_path,
            output_path=output_path,
            quiet=quiet,
            use_tqdm=False,
        )

    def _run_with_args(self, func, **kwargs) -> ScraperResult:
        """Run a scraper function with output capture."""
        # Save original print
        self._original_print = builtins.print
        self._output_lines = []
        self._progress = ProgressTracker()

        def captured_print(*args, **kwargs):
            """Captured print function that logs output and detects progress."""
            text = " ".join(str(a) for a in args)
            self._output_lines.append(text)

            # Detect progress line from fetch scripts
            if text.startswith("Fetch progress:"):
                try:
                    parts = text.split(":")[1].strip().split("/")
                    idx = int(parts[0])
                    total = int(parts[1])
                    self._progress.idx = idx
                    self._progress.total = total
                    self._progress.running = True
                    progress = min(idx / total, 1.0) * 0.45 + 0.5
                    if self._on_progress:
                        self._on_progress(
                            f"Fetch 中 (已處理 {idx}/{total} 行)...",
                            progress
                        )
                except Exception:
                    self._original_print(text)
            else:
                self._log(text)
                self._original_print(text)

        # Replace print
        builtins.print = captured_print

        try:
            func(**kwargs)
            output = "\n".join(self._output_lines)
            return ScraperResult.success_result(output=output)
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Script execution error: {error_details}")
            return ScraperResult.error_result(str(ex))
        finally:
            # Restore original print
            builtins.print = self._original_print

    def _log(self, message: str):
        """Log a message via the logger and callback."""
        if self._on_log:
            self._on_log(message)

    def parse_collected_count(self, output: str) -> int:
        """Parse the number of collected entries from output.

        Args:
            output: Script output string.

        Returns:
            Number of collected entries, or 0 if not found.
        """
        for line in output.split("\n"):
            if "Done!" in line or "entries" in line.lower():
                match = re.search(r'(\d+)', line)
                if match:
                    return int(match.group(1))
        return 0
