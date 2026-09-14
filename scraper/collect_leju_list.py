"""Collects sale listing IDs from leju.com.tw (樂居) based on a provided URL.

This script navigates to a leju.com.tw ``object_list`` page, calls the
underlying listing API (``/api/search/forsale/sales_list``) from inside the
browser context to bypass Cloudflare, and collects the ``hash_sales_id`` of
every matching object across all pagination pages. The collected IDs are saved
to a joblib file for later use by ``fetch_leju_info.py``.

Notes on the site:
    - leju.com.tw is protected by Cloudflare, so plain ``requests`` returns 403.
      We use a real Chromium browser (DrissionPage) and issue the API ``fetch``
      from within the loaded page so the request carries the proper cookies.
    - The listing data is loaded client-side via the JSON API rather than being
      embedded in the server-rendered HTML.

Environment Variables:
    LejuSaleURL: The base URL for the leju.com.tw sale (object_list) listings.

Functions:
    main: The main function to execute the listing collection process.
"""

import json
import os
import random
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import joblib
import typer
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page

URL = os.environ.get("LejuSaleURL", "")

# The frontend object_list page and the backing JSON API share the same query
# parameters; the API simply adds a ``page`` parameter for pagination.
API_BASE = "https://api.leju.com.tw/api/search/forsale/sales_list"

# JS snippet executed in the page to fetch a URL and stash the text result on
# window globals (DrissionPage's run_js cannot await directly).
_FETCH_JS = """
window.__leju_done = false;
window.__leju_body = '';
fetch(arguments[0], {headers: {'Accept': 'application/json'}})
    .then(r => r.text())
    .then(t => { window.__leju_body = t; window.__leju_done = true; })
    .catch(e => { window.__leju_body = 'ERR:' + e; window.__leju_done = true; });
"""


def wait_passed_cloudflare(page: ChromiumPage, max_wait: int = 90) -> bool:
    """Wait until the Cloudflare interstitial ('請稍候...') is gone.

    Args:
        page: DrissionPage page instance.
        max_wait: Maximum seconds to wait.

    Returns:
        True if the challenge cleared, False if it timed out.
    """
    for _ in range(max_wait):
        title = page.title or ""
        if "請稍候" not in title and "稍候" not in title and "Just a moment" not in title:
            return True
        time.sleep(1)
    return False


def fetch_json_in_page(page: ChromiumPage, url: str, timeout: int = 30) -> dict | None:
    """Fetch a JSON URL from within the page context and return the parsed dict.

    Args:
        page: DrissionPage page instance (already on a leju.com.tw page).
        url: The API URL to fetch.
        timeout: Maximum seconds to wait for the fetch to complete.

    Returns:
        Parsed JSON dict, or None on failure.
    """
    page.run_js(_FETCH_JS, url)
    for _ in range(timeout):
        if page.run_js("return window.__leju_done;"):
            break
        time.sleep(1)
    body = page.run_js("return window.__leju_body;")
    if not body or body.startswith("ERR:"):
        print(f"  Fetch failed: {body[:120] if body else 'empty'}")
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        print(f"  JSON decode error: {e}")
        return None


def build_api_url(base_list_url: str, page_no: int) -> str:
    """Build the sales_list API URL from a frontend object_list URL.

    Copies all query parameters from the frontend URL and appends/overrides the
    ``page`` parameter.

    Args:
        base_list_url: The frontend object_list URL.
        page_no: 1-based page number.

    Returns:
        The API URL for the requested page.
    """
    parsed = urlparse(base_list_url)
    query_params = parse_qs(parsed.query)
    query_params["page"] = [str(page_no)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(scheme="https", netloc="api.leju.com.tw", path="/api/search/forsale/sales_list", query=new_query))


def extract_ids_from_page(data: dict) -> list[str]:
    """Extract hash_sales_id values from a sales_list API response.

    Args:
        data: Parsed API response dict.

    Returns:
        List of hash_sales_id strings.
    """
    ids: list[str] = []
    items = (data.get("data") or {}).get("sales_list") or []
    for item in items:
        hid = item.get("hash_sales_id")
        if hid:
            ids.append(hid)
    return ids


def main(url: str = URL, output_path: str = "cache/leju_listings.jbl", max_pages: int = 50, quiet: bool = False) -> list[str]:
    """Main function to collect leju sale listing IDs.

    When ``output_path`` is provided, the collected IDs are also saved to a
    joblib file for CLI usage; GUI callers can pass an empty ``output_path`` to
    skip saving and use the returned list directly.

    Args:
        url: The frontend object_list URL (defaults to LejuSaleURL env var)
        output_path: Path to save the collected IDs (empty to skip saving)
        max_pages: Maximum number of pages to scrape
        quiet: Whether to run in headless mode

    Returns:
        List of collected hash_sales_id strings.
    """
    if not url:
        print("Error: URL is not set!")
        print("Example: export LejuSaleURL='https://www.leju.com.tw/object_list?city_code=F&post_codes=220'")
        print("Or use --url parameter: python collect_leju_list.py --url 'https://www.leju.com.tw/object_list?...'")
        raise ValueError("URL not set")

    page = create_browser(headless=quiet)
    print("Browser initialized.")

    # Load the frontend page first to pass Cloudflare and establish cookies.
    navigate_to_a_page(page, url, wait_selector="", timeout=15)
    if not wait_passed_cloudflare(page):
        print("Warning: Cloudflare challenge did not clear within timeout.")
    time.sleep(random.random() * 2 + 1)

    all_ids: list[str] = []
    seen: set[str] = set()
    last_page = 1

    for page_no in range(1, max_pages + 1):
        api_url = build_api_url(url, page_no)
        print(f"Page {page_no}: {api_url[:120]}...")

        data = fetch_json_in_page(page, api_url)
        if not data or data.get("status") != "success":
            print("  No/invalid response. Stopping.")
            break

        ids = extract_ids_from_page(data)
        new_ids = [i for i in ids if i not in seen]
        seen.update(new_ids)
        all_ids.extend(new_ids)

        meta = data.get("meta") or {}
        last_page = int(meta.get("last_page") or page_no)
        total = meta.get("total")
        print(f"  Found {len(new_ids)} new IDs (page {page_no}/{last_page}, total={total})")
        print(f"  Total unique IDs so far: {len(all_ids)}")

        if page_no >= last_page:
            print("Reached last page. Exiting...")
            break

        time.sleep(random.random() * 2 + 1)

    if output_path:
        joblib.dump(all_ids, output_path)

    print(f"Done! Collected {len(all_ids)} entries in total.")

    page.quit()
    return all_ids


if __name__ == "__main__":
    typer.run(main)
