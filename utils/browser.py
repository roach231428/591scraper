"""Shared browser utilities for 591.com.tw scrapers.

This module provides common browser creation and navigation functions
used across multiple scraper scripts.
"""

import random
import time

from DrissionPage import ChromiumPage, ChromiumOptions


def create_browser(headless: bool = False) -> ChromiumPage:
    """Create a DrissionPage browser instance with anti-detection settings.
    
    Args:
        headless: Whether to run the browser in headless mode.
        
    Returns:
        A configured ChromiumPage instance.
    """
    opts = ChromiumOptions()
    if headless:
        opts.headless()
    opts.set_argument("--disable-blink-features=AutomationControlled")
    opts.set_argument("--no-first-run")
    opts.set_argument("--no-default-browser-check")
    return ChromiumPage(opts)


def navigate_to_a_page(page: ChromiumPage, url: str, wait_selector: str = "", timeout: float = 5) -> None:
    """Navigate to a page and optionally wait for content to load.
    
    Args:
        page: DrissionPage page instance.
        url: The URL to navigate to.
        wait_selector: CSS selector to wait for after page load. Empty string skips waiting.
        timeout: Timeout in seconds for waiting for content.
    """
    try:
        page.get(url)
    except Exception as e:
        print(f"Failed to navigate to the page: {e}")
        raise e

    if wait_selector:
        try:
            page.wait.eles_loaded(f"css:{wait_selector}", timeout=timeout)
            print("Page content loaded.")
        except Exception:
            print(f"Expected content ({wait_selector}) not found, proceeding anyway.")

    time.sleep(random.random())
