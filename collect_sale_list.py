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
import re
import time
import random
from typing import Optional
from urllib.parse import urlparse, parse_qs, urljoin, urlencode, urlunparse

import typer
import joblib
from DrissionPage import ChromiumPage, ChromiumOptions

URL = os.environ.get("X591SaleURL", "")


def create_browser(headless: bool = False) -> ChromiumPage:
    """Create a DrissionPage browser instance with anti-detection settings."""
    opts = ChromiumOptions()
    if headless:
        opts.headless()
    opts.set_argument("--disable-blink-features=AutomationControlled")
    opts.set_argument("--no-first-run")
    opts.set_argument("--no-default-browser-check")
    return ChromiumPage(opts)


def navigate_to_a_page(page: ChromiumPage, url: str):
    """Navigate to a page and wait for listing items to load."""
    try:
        page.get(url)
    except Exception as e:
        print(f"Failed to navigate to the page: {e}")
        raise e

    # Wait for listing items to load
    # Sale page uses .ware-item class for each listing
    try:
        page.wait.eles_loaded("css:.ware-item", timeout=5)
        print("Page content loaded.")
    except Exception:
        print("Listing items not found, proceeding anyway (might be empty results).")

    time.sleep(random.random() * 2 + 1)


def extract_listing_id_from_href(href: str) -> Optional[str]:
    """Extract listing ID from href.
    
    Sale URL format: https://sale.591.com.tw/home/house/detail/2/20342836.html
    ID is the number before .html in the path.
    """
    if not href:
        return None
    
    # Match pattern: /detail/2/{id}.html
    match = re.search(r'/detail/\d+/(\d+)\.html', href)
    if match:
        return match.group(1)
    
    return None


def main(output_path: str = "cache/sale_listings.jbl", max_pages: int = 10, quiet: bool = False):
    """Main function to collect sale listing IDs.
    
    Args:
        output_path: Path to save the collected IDs (default: cache/sale_listings.jbl)
        max_pages: Maximum number of pages to scrape
        quiet: Whether to run in headless mode
    """
    if not URL:
        print("Error: X591SaleURL environment variable is not set!")
        print("Example: export X591SaleURL='https://sale.591.com.tw/?regionid=3&section=43,44'")
        raise ValueError("X591SaleURL not set")
    
    try:
        region_id = parse_qs(urlparse(URL).query).get("regionid", [None])[0]
        if not region_id:
            print("Warning: URL does not have a 'regionid' query argument, but continuing...")
    except AttributeError as e:
        print(f"Error parsing URL: {e}")
        raise e

    page = create_browser(headless=quiet)
    print("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, URL)

    listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")

        # Extract listing IDs from .ware-item elements
        # Each .ware-item has data-id attribute containing the listing ID
        ware_items = page.eles("css:.ware-item", timeout=5)
        
        for item in ware_items:
            # Try data-id attribute first
            data_id = item.attr("data-id")
            if data_id and data_id.isdigit():
                listings.add(data_id)

        print(f"  Found {len(listings)} unique IDs so far")

        if i == max_pages - 1:
            print("Reached maximum pages. Exiting...")
            break

        # Pagination via URL parameter 'firstRow'
        # Get current URL and extract firstRow parameter
        current_url = page.url
        current_params = parse_qs(urlparse(current_url).query)
        
        # Get current firstRow value (default to 0)
        first_row = int(current_params.get("firstRow", ["0"])[0])
        page_size = 30  # 591 shows 30 items per page
        
        # Calculate next page's firstRow
        next_first_row = first_row + page_size
        
        # Check if there are more items by looking at current page count
        ware_items_count = len(page.eles("css:.ware-item"))
        if ware_items_count < 10:  # If less than 10 items, probably last page
            print("No more pages to scrape. Exiting...")
            break
        
        # Build next page URL with updated firstRow
        parsed = urlparse(current_url)
        query_params = parse_qs(parsed.query)
        query_params["firstRow"] = [str(next_first_row)]
        
        # Rebuild URL with new firstRow parameter
        new_query = urlencode(query_params, doseq=True)
        next_url = urlunparse(parsed._replace(query=new_query))
        
        print(f"  Navigating to page with firstRow={next_first_row}")
        page.get(next_url)
        time.sleep(random.random() * 2 + 1)

        # Wait for new page content
        try:
            page.wait.eles_loaded("css:.ware-item", timeout=5)
        except Exception:
            pass

    joblib.dump(list(listings), output_path)
    print(f"Done! Collected {len(listings)} entries.")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
