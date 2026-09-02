import re
import time
import shutil
import random
import logging
import csv
from datetime import date
from typing import Optional, Any

import typer
import joblib
from tqdm import tqdm
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    before_sleep_log,
    RetryError,
    retry_if_exception_type,
)
from DrissionPage import ChromiumPage

from utils.post_processing import adjust_price, auto_marking, parse_price
from utils.browser import create_browser, navigate_to_a_page

LOGGER = logging.getLogger(__name__)


class PageLoadError(Exception):
    pass


class NotExistException(Exception):
    pass


def get_attributes(page: ChromiumPage):
    result = {}

    # 養寵物
    service_el = page.ele("css:section.service", timeout=2)
    if service_el:
        result["養寵物"] = "No" if "不可養寵物" in (service_el.text or "") else "Yes"
    else:
        result["養寵物"] = None

    # 租金含、車位費、管理費
    for label_name in ("租金含", "車位費", "管理費"):
        label_el = page.ele(f"text={label_name}", timeout=1)
        if label_el:
            parent = label_el.parent()
            text_el = parent.ele("css:div.text", timeout=1) if parent else None
            result[label_name] = text_el.text.strip() if text_el else ""
        else:
            result[label_name] = ""

    # 提供設備
    facility_el = page.ele("css:div.service-facility", timeout=2)
    if facility_el:
        items = facility_el.eles("css:dl:not(.del) dd")
        result["提供設備"] = ", ".join(item.text.strip() for item in items if item.text)
    else:
        result["提供設備"] = ""

    return result


@retry(
    reraise=False,
    retry=retry_if_exception_type(PageLoadError),
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    before_sleep=before_sleep_log(LOGGER, logging.INFO),
)
def get_page(page: ChromiumPage, listing_id):
    navigate_to_a_page(page, f"https://rent.591.com.tw/home/{listing_id}".strip(), wait_selector="div.title")
    title_el = page.ele("css:div.title", timeout=5)
    if title_el and "不存在" in (title_el.text or ""):
        raise NotExistException()


def get_listing_info(page: ChromiumPage, listing_id: str):
    try:
        get_page(page, listing_id)
    except RetryError:
        typer.echo("RetryError encountered... Trying to parse whatever is on the page.")

    result: dict[str, Any] = {"id": listing_id}

    h1 = page.ele("css:.title h1", timeout=3)
    result["title"] = h1.text.strip() if h1 else ""

    addr_el = page.ele("css:div.address div", timeout=3)
    result["addr"] = addr_el.text.strip() if addr_el else ""

    complex_el = page.ele("css:div.address p a", timeout=2)
    if complex_el:
        result["社區"] = complex_el.text.strip()

    price_el = page.ele("css:div.house-price", timeout=3)
    result["price"] = parse_price(price_el.text if price_el else "")

    desc_el = page.ele("css:div.house-condition-content", timeout=3)
    result["desc"] = desc_el.text.strip() if desc_el else ""

    poster_el = page.ele("css:p.base-info-pc", timeout=3)
    result["poster"] = re.sub(r"\s+", " ", poster_el.text.strip()) if poster_el else ""

    result.update(get_attributes(page))
    return result


def load_existing_data(data_path: str) -> tuple[list[dict[str, Any]], set[str]]:
    """Load existing CSV data and return (records, existing_ids)."""
    records: list[dict[str, Any]] = []
    existing_ids: set[str] = set()

    with open(data_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
            existing_ids.add(row.get("id", ""))

    return records, existing_ids


def save_records(records: list[dict[str, Any]], output_path: str, desc_column: bool = True) -> None:
    """Save records to CSV file."""
    if not records:
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            pass
        return

    # Determine all fields from records
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main(
    source_path: str = "cache/listings.jbl",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    quiet: bool = False,
    use_tqdm: bool = True,
):
    # joblib is used here to maintain compatibility with the existing
    # collect_list.py output format (.jbl files).
    listing_ids = joblib.load(source_path)

    existing_records: list[dict[str, Any]] = []
    if data_path:
        existing_records, existing_ids = load_existing_data(data_path)
        # Filter out already fetched IDs
        listing_ids = [id_ for id_ in listing_ids if id_ not in existing_ids]
        print(f"After filtering existing: {len(listing_ids)} listings to fetch")

    if limit > 0:
        listing_ids = listing_ids[:limit]

    print(f"Collecting {len(listing_ids)} entries...")

    page = create_browser(headless=quiet)

    data: list[dict[str, Any]] = []
    total = len(listing_ids)
    iterator = tqdm(listing_ids, ncols=100) if use_tqdm else listing_ids
    for idx, id_ in enumerate(iterator, start=1):
        try:
            data.append(get_listing_info(page, id_))
        except NotExistException:
            LOGGER.warning(f"Does not exist: {id_}")
            pass
        print(f"Fetch progress: {idx}/{total}")
        LOGGER.info(f"Fetch progress: {idx}/{total}")
        time.sleep(random.random() * 5)

    # Add optional fields if missing
    optional_fields = ("租金含", "車位費", "管理費")
    for record in data:
        for field in optional_fields:
            if field not in record:
                record[field] = None

    # Apply post-processing
    data = auto_marking(data)
    data = adjust_price(data)

    # Add fetched date
    for record in data:
        record["fetched"] = date.today().isoformat()

    # Merge with existing records
    if existing_records:
        data = existing_records + data

    if output_path is None and data_path is None:
        # default output path
        output_path = "cache/df_listings.csv"
    elif output_path is None and data_path:
        output_path = data_path
        shutil.copy(data_path, data_path + ".bak")

    # Add link column
    for record in data:
        record["link"] = "https://rent.591.com.tw/rent-detail-" + str(record.get("id", "")) + ".html"

    # Define output column order
    column_ordering = [
        "mark",
        "title",
        "price",
        "price_adjusted",
        "link",
        "addr",
        "社區",
        "車位費",
        "管理費",
        "poster",
        "養寵物",
        "提供設備",
        # TODO: Restore support for these fields
        # "格局",
        # "坪數",
        # "樓層",
        # "型態",
        "id",
        "fetched",
        "desc",
    ]

    # Ensure all records have the required fields
    for record in data:
        for field in column_ordering:
            if field not in record:
                record[field] = ""

    # Sample output
    sample_size = min(len(data), 10)
    if sample_size > 0:
        print("Sample records:")
        for record in data[:sample_size]:
            print({k: v for k, v in record.items() if k != "desc"})

    # Save to CSV with defined column order
    save_records(data, output_path, desc_column=False)
    print("Finished!")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
