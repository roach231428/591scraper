"""Collects sale listing IDs from 591.com.tw based on a provided URL.

This script navigates to a specified 591.com.tw sale listing page,
extracts listing IDs, and saves them to a joblib file.
It supports pagination to collect IDs from multiple pages.

Environment Variables:
    X591SaleURL: The base URL for the 591.com.tw sale listings. This URL
                 must contain a 'region' query parameter.

Functions:
    main: The main function to execute the listing collection process.
"""

import os
import random
import time
from urllib.parse import parse_qs, urlparse

import typer
import joblib
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page
from utils.pagination import build_next_url_by_first_row, wait_for_page_content

URL = os.environ.get("X591SaleURL", "")


def extract_ids_from_ware_items(page: ChromiumPage) -> set[str]:
    """Extract listing IDs from .ware-item elements on the page.
    
    Each .ware-item has data-id attribute containing the listing ID.
    
    Args:
        page: DrissionPage page instance.
        
    Returns:
        Set of listing IDs extracted from the page.
    """
    listings: set[str] = set()
    ware_items = page.eles("css:.ware-item", timeout=5)
    
    for item in ware_items:
        data_id = item.attr("data-id")
        if data_id and data_id.isdigit():
            listings.add(data_id)
    
    return listings


def main(url: str = URL, output_path: str = "cache/sale_listings.jbl", max_pages: int = 10, quiet: bool = False):
    """Main function to collect sale listing IDs.
    
    Args:
        url: The URL for the 591.com.tw sale listings (defaults to X591SaleURL env var)
        output_path: Path to save the collected IDs (default: cache/sale_listings.jbl)
        max_pages: Maximum number of pages to scrape
        quiet: Whether to run in headless mode
    """
    if not url:
        print("Error: URL is not set!")
        print("Example: export X591SaleURL='https://sale.591.com.tw/?regionid=3&section=43,44'")
        print("Or use --url parameter: python collect_sale_list.py --url 'https://sale.591.com.tw/...'")
        raise ValueError("URL not set")
    
    try:
        region_id = parse_qs(urlparse(url).query).get("regionid", [None])[0]
        if not region_id:
            print("Warning: URL does not have a 'regionid' query argument, but continuing...")
    except AttributeError as e:
        print(f"Error parsing URL: {e}")
        raise e

    page = create_browser(headless=quiet)
    print("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, url, wait_selector=".ware-item", timeout=5)

    listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")

        # Extract listing IDs from .ware-item elements
        listings.update(extract_ids_from_ware_items(page))

        print(f"  Found {len(listings)} unique IDs so far")

        if i == max_pages - 1:
            print("Reached maximum pages. Exiting...")
            break

        # Check if there are more items by looking at current page count
        ware_items_count = len(page.eles("css:.ware-item"))
        if ware_items_count < 10:  # If less than 10 items, probably last page
            print("No more pages to scrape. Exiting...")
            break
        
        # Pagination via URL parameter 'firstRow'
        next_url = build_next_url_by_first_row(page.url, page_size=30)
        
        print(f"  Navigating to page with firstRow={int(parse_qs(urlparse(next_url).query).get('firstRow', ['0'])[0])}")
        page.get(next_url)
        time.sleep(random.random() * 2 + 1)

        # Wait for new page content
        wait_for_page_content(page, ".ware-item", timeout=5)

    joblib.dump(list(listings), output_path)
    print(f"Done! Collected {len(listings)} entries.")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
