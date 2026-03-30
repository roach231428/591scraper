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
import time
import random
from urllib.parse import urlparse, parse_qs

import typer
import joblib
from DrissionPage import ChromiumPage, ChromiumOptions

URL = os.environ["X591URL"]


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
    try:
        page.get(url)
    except Exception as e:
        print(f"Failed to navigate to the page: {e}")
        raise e

    # Wait for listing items to load
    try:
        page.wait.eles_loaded("css:.item-info-title a", timeout=10)
        typer.echo("Page content loaded.")
    except Exception:
        typer.echo("Listing items not found, proceeding anyway (might be a single page result).")

    time.sleep(random.random() * 2 + 1)


def main(output_path: str = "cache/listings.jbl", max_pages: int = 10, quiet: bool = False):
    try:
        region = parse_qs(urlparse(URL).query)["region"][0]
    except (AttributeError, KeyError) as e:
        print("The URL must have a 'region' query argument!")
        raise e

    page = create_browser(headless=quiet)
    typer.echo("Browser initialized.")

    # Navigate to the specified URL
    navigate_to_a_page(page, URL)

    listings: set[str] = set()
    for i in range(max_pages):
        print(f"Page {i + 1}")

        # Extract listing IDs from links
        links = page.eles("css:.item-info-title a")
        for link in links:
            href = link.attr("href") or ""
            match = re.search(r"/(\d+)(?:\.html)?$", href)
            if match:
                listings.add(match.group(1))

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
        try:
            page.wait.eles_loaded("css:.item-info-title a", timeout=10)
        except Exception:
            pass

    joblib.dump(list(listings), output_path)
    print(f"Done! Collected {len(listings)} entries.")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
