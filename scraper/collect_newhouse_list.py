"""Collects new house listing IDs from 591.com.tw based on a provided URL.

This script navigates to a specified 591.com.tw new house listing page,
extracts listing IDs, and saves them to a joblib file.
It supports pagination to collect IDs from multiple pages.

Environment Variables:
    X591NewHouseURL: The base URL for the 591.com.tw new house listings. This URL
                     must contain a 'region' query parameter.

Functions:
    main: The main function to execute the listing collection process.
"""

import os
import random
import time
from typing import List
from urllib.parse import parse_qs, urlencode, urlunparse, urlparse

import typer
import joblib
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page
from utils.extractor import extract_ids_from_json_ld
from utils.pagination import build_next_url_by_first_row, wait_for_page_content

URL = os.environ.get("X591NewHouseURL", "")


def collect_ids_from_page(page: ChromiumPage) -> List[str]:
    """Extract listing IDs from the current page using JSON-LD structured data.
    
    Args:
        page: DrissionPage page instance.
        
    Returns:
        List of listing IDs extracted from the page.
    """
    html = page.html
    return extract_ids_from_json_ld(html)


def main(url: str = URL, output_path: str = "cache/newhouse_listings.jbl", max_pages: int = 10, quiet: bool = False) -> list[str]:
    """Main function to collect new house listing IDs.

    When ``output_path`` is provided, the collected IDs are also saved to a
    joblib file for CLI usage; GUI callers can pass an empty
    ``output_path`` to skip saving and use the returned list directly.

    Args:
        url: The URL for the 591.com.tw new house listings (defaults to X591NewHouseURL env var)
        output_path: Path to save the collected IDs (empty to skip saving)
        max_pages: Maximum number of pages to scrape
        quiet: Whether to run in headless mode

    Returns:
        List of collected listing IDs.
    """
    if not url:
        print("Error: URL is not set!")
        print("Example: export X591NewHouseURL='https://newhouse.591.com.tw/?regionid=3&sectionid=43'")
        print("Or use --url parameter: python collect_newhouse_list.py --url 'https://newhouse.591.com.tw/...'")
        raise ValueError("URL not set")
    
    try:
        region_id = parse_qs(urlparse(url).query).get("regionid", [None])[0]
        section_id = parse_qs(urlparse(url).query).get("sectionid", [None])[0]
        if not region_id or not section_id:
            print("Warning: URL does not have 'regionid' and 'sectionid' query arguments, but continuing...")
    except AttributeError as e:
        print(f"Error parsing URL: {e}")
        raise e

    page = create_browser(headless=quiet)
    print("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, url, wait_selector="script[type='application/ld+json']", timeout=5)

    all_listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")

        new_ids = set(collect_ids_from_page(page))
        ids_to_add = new_ids - all_listings
        all_listings.update(new_ids)

        print(f"  Found {len(ids_to_add)} new IDs on this page")
        print(f"  Total unique IDs so far: {len(all_listings)}")

        if i == max_pages - 1:
            print("Reached maximum pages. Exiting...")
            break

        # Pagination via URL parameter 'firstRow'
        next_url = build_next_url_by_first_row(page.url, page_size=30)
        
        print(f"  Navigating to page with firstRow={int(parse_qs(urlparse(next_url).query).get('firstRow', ['0'])[0])}")
        page.get(next_url)
        time.sleep(random.random() * 2 + 1)

        # Wait for new page content
        wait_for_page_content(page, "script[type='application/ld+json']", timeout=5)

    id_list = list(all_listings)

    if output_path:
        joblib.dump(id_list, output_path)

    print(f"Done! Collected {len(id_list)} entries in total.")

    page.quit()
    return id_list


if __name__ == "__main__":
    typer.run(main)
