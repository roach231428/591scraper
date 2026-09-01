"""Shared pagination utilities for 591.com.tw scrapers.

This module provides common pagination functions used across multiple
scraper scripts that need to navigate through multiple pages.
"""

import random
import time
from urllib.parse import parse_qs, urlencode, urlunparse, urlparse

from DrissionPage import ChromiumPage


def build_next_url_by_first_row(current_url: str, page_size: int = 30) -> str:
    """Build the next page URL by incrementing the 'firstRow' query parameter.
    
    Used by 591 sale and newhouse listing pages that use firstRow-based pagination.
    
    Args:
        current_url: The current page URL.
        page_size: Number of items per page (default: 30).
        
    Returns:
        The URL for the next page.
    """
    current_params = parse_qs(urlparse(current_url).query)
    first_row = int(current_params.get("firstRow", ["0"])[0])
    next_first_row = first_row + page_size
    
    parsed = urlparse(current_url)
    query_params = parse_qs(parsed.query)
    query_params["firstRow"] = [str(next_first_row)]
    
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def wait_for_page_content(page: ChromiumPage, wait_selector: str, timeout: float = 5) -> bool:
    """Wait for page content to load and return success status.
    
    Args:
        page: DrissionPage page instance.
        wait_selector: CSS selector to wait for.
        timeout: Timeout in seconds.
        
    Returns:
        True if content loaded successfully, False otherwise.
    """
    try:
        page.wait.eles_loaded(f"css:{wait_selector}", timeout=timeout)
        return True
    except Exception:
        return False


def wait_for_next_page(page: ChromiumPage, next_href: str, wait_selector: str, 
                       page_size: int = 30) -> bool:
    """Wait for the next page to load after clicking or navigating.
    
    Args:
        page: DrissionPage page instance.
        next_href: The href of the next page (for logging).
        wait_selector: CSS selector to wait for on the new page.
        page_size: Number of items per page (default: 30).
        
    Returns:
        True if content loaded successfully, False otherwise.
    """
    time.sleep(random.random() * 2 + 1)
    return wait_for_page_content(page, wait_selector, timeout=5)
