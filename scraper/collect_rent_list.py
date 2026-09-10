"""Collects rental listing IDs from 591.com.tw based on a provided URL.

This script navigates to a specified 591.com.tw rental listing page,
extracts listing IDs, and saves them to a joblib file.

It supports pagination to collect IDs from multiple pages.

Environment Variables:
    X591URL: The base URL for the 591.com.tw rental listings. This URL
             must contain a 'region' query parameter.

Functions:
    main: The main function to execute the listing collection process.
"""

import os
import re
import random
import time
from urllib.parse import urlparse, parse_qs

import typer
import joblib
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page
from utils.extractor import extract_id_from_href
from utils.pagination import wait_for_page_content

URL = os.environ.get("X591URL", "")


def extract_ids_from_links(page: ChromiumPage) -> set[str]:
    """Extract listing IDs from links on the page.
    
    Args:
        page: DrissionPage page instance.
        
    Returns:
        Set of listing IDs extracted from the page.
    """
    listings: set[str] = set()
    links = page.eles("css:.item-info-title a")
    for link in links:
        href = link.attr("href") or ""
        listing_id = extract_id_from_href(href, pattern="default")
        if listing_id:
            listings.add(listing_id)
    return listings


def main(url: str = URL, output_path: str = "cache/listings.jbl", max_pages: int = 10, quiet: bool = False) -> list[str]:
    """Collect rental listing IDs and return them as a list.

    When ``output_path`` is provided, the collected IDs are also saved to a
    joblib file for CLI usage; GUI callers can pass an empty
    ``output_path`` to skip saving and use the returned list directly.

    Args:
        url: The URL for the 591.com.tw rental listings.
        output_path: Path to save the collected IDs (empty to skip saving).
        max_pages: Maximum number of pages to scrape.
        quiet: Whether to run in headless mode.

    Returns:
        List of collected listing IDs.
    """
    if not url:
        print("Error: URL is not set!")
        print("Example: export X591URL='https://rent.591.com.tw/...'")
        print("Or use --url parameter: python collect_rent_list.py --url 'https://rent.591.com.tw/...'")
        raise ValueError("URL not set")
    
    try:
        region = parse_qs(urlparse(url).query)["region"][0]
    except (AttributeError, KeyError) as e:
        print("The URL must have a 'region' query argument!")
        raise e

    page = create_browser(headless=quiet)
    typer.echo("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, url, wait_selector=".item-info-title a", timeout=10)

    all_listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")

        new_ids = extract_ids_from_links(page)
        ids_to_add = new_ids - all_listings
        all_listings.update(new_ids)

        print(f"  Found {len(ids_to_add)} new IDs on this page")
        print(f"  Total unique IDs so far: {len(all_listings)}")

        if i == max_pages - 1:
            typer.echo("Reached maximum pages. Exiting...")
            break

        # Find next page link
        next_page = page.ele("text=下一頁", timeout=3)

        if not next_page:
            typer.echo("No more pages to scrape. Exiting...")
            break

        next_href = (next_page.attr("href") or "").strip()
        if next_href in ("", "#"):
            typer.echo("No more pages to scrape. Exiting...")
            break

        next_page.click()
        time.sleep(random.random() * 2 + 1)

        # Wait for new page content
        wait_for_page_content(page, ".item-info-title a", timeout=10)

    id_list = list(all_listings)

    if output_path:
        joblib.dump(id_list, output_path)

    print(f"Done! Collected {len(id_list)} entries in total.")

    page.quit()
    return id_list


if __name__ == "__main__":
    typer.run(main)
