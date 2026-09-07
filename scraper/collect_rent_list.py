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
from utils.persistence import load_existing_ids

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


def main(url: str = URL, output_path: str = "cache/listings.jbl", max_pages: int = 10, quiet: bool = False):
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

    existing_ids = load_existing_ids(output_path)
    if existing_ids:
        print(f"Loaded {len(existing_ids)} existing IDs from {output_path}")

    page = create_browser(headless=quiet)
    typer.echo("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, url, wait_selector=".item-info-title a", timeout=10)

    all_listings = set(existing_ids)
    for i in range(max_pages):
        print(f"Page {i + 1}")

        new_ids = extract_ids_from_links(page)
        ids_to_add = new_ids - existing_ids
        all_listings.update(ids_to_add)

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

    joblib.dump(list(all_listings), output_path)
    print(f"Done! Collected {len(all_listings)} entries in total ({len(existing_ids)} existing + {len(all_listings - existing_ids)} new).")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
