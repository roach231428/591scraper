
"""Fetches detailed information for leju.com.tw (樂居) sale listings.

This script reads ``hash_sales_id`` values from a joblib file (produced by
``collect_leju_list.py``), navigates to each object's detail page
(``https://www.leju.com.tw/sales/{hash_sales_id}``), extracts the full object
information from the server-rendered ``__NUXT_DATA__`` payload, and appends the
results to a CSV file.

Notes on the site:
    - leju.com.tw is protected by Cloudflare, so plain ``requests`` returns 403.
      We use a real Chromium browser (DrissionPage).
    - The detail data is embedded in the page's ``__NUXT_DATA__`` JSON under the
      key ``salesObjectInfo-{hash_sales_id}``. The dedicated detail API requires
      a per-object ``lejuToken``, so parsing the SSR payload is the most robust
      approach.

Functions:
    main: The main function to execute the sale info fetching process.
"""

import json
import logging
import os
import random
import re
import time
from datetime import date
from typing import Any, Optional

import joblib
import typer
from DrissionPage import ChromiumPage
from tenacity import RetryError, retry, stop_after_attempt, wait_random
from tqdm import tqdm

from utils.browser import create_browser, navigate_to_a_page
from utils.persistence import (
    append_record,
    auto_detect_csv_path,
    clean_record_strings,
    deal_paths,
    load_existing_csv_data,
    print_sample_records,
)

LOGGER = logging.getLogger(__name__)

DETAIL_BASE = "https://www.leju.com.tw/sales/"

# Direction code -> Chinese mapping used by leju.
DIRECTION_MAP = {
    "N": "北",
    "S": "南",
    "E": "東",
    "W": "西",
    "NE": "東北",
    "NW": "西北",
    "SE": "東南",
    "SW": "西南",
}


class NotExistException(Exception):
    pass


def wait_passed_cloudflare(page: ChromiumPage, max_wait: int = 90) -> bool:
    """Wait until the Cloudflare interstitial ('請稍候...') is gone."""
    for _ in range(max_wait):
        title = page.title or ""
        if "請稍候" not in title and "稍候" not in title and "Just a moment" not in title:
            return True
        time.sleep(1)
    return False


def parse_nuxt_payload(html: str) -> list:
    """Extract and JSON-parse the ``__NUXT_DATA__`` payload array from HTML.

    Args:
        html: The page HTML.

    Returns:
        The raw serialized payload list, or an empty list if not found.
    """
    m = re.search(r'id="__NUXT_DATA__">(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return []


def deref_factory(data: list):
    """Build a resolver for the Nuxt 3 serialized (index-referenced) payload.

    Args:
        data: The raw serialized payload list.

    Returns:
        A function that resolves an index reference into a plain Python object.
    """

    def deref(idx: Any, depth: int = 0, max_depth: int = 12) -> Any:
        if depth > max_depth:
            return None
        val = data[idx] if isinstance(idx, int) and 0 <= idx < len(data) else idx
        if isinstance(val, dict):
            return {k: deref(v, depth + 1, max_depth) for k, v in val.items()}
        if isinstance(val, list):
            if val and val[0] in ("Reactive", "ShallowReactive"):
                return deref(val[1], depth + 1, max_depth)
            if val and val[0] == "EmptyRef":
                return None
            if val and val[0] == "Ref":
                return deref(val[1], depth + 1, max_depth)
            return [deref(v, depth + 1, max_depth) for v in val]
        return val

    return deref


def extract_object_info(html: str, listing_id: str) -> dict[str, Any]:
    """Extract the salesObjectInfo dict for a listing from the page HTML.

    Args:
        html: The detail page HTML.
        listing_id: The hash_sales_id being extracted.

    Returns:
        The raw object info dict, or an empty dict if not found.
    """
    payload = parse_nuxt_payload(html)
    if not payload:
        return {}
    deref = deref_factory(payload)
    resolved = deref(1)  # root node
    if not isinstance(resolved, dict):
        return {}
    data_slot = resolved.get("data") or {}
    key = f"salesObjectInfo-{listing_id}"
    info = data_slot.get(key)
    return info if isinstance(info, dict) else {}


def flatten_info(info: dict[str, Any], listing_id: str) -> dict[str, Any]:
    """Flatten the raw object info into a CSV-friendly record.

    The output keys follow the same header order as ``cache/sale_results.csv``
    (produced by ``fetch_sale_info.py``). Fields that leju does not provide
    (e.g. 現況, 裝潢程度, 帶租約, 生活機能, 附近交通, 有效期) are omitted.

    Args:
        info: The raw salesObjectInfo dict.
        listing_id: The hash_sales_id.

    Returns:
        A flat record dict.
    """
    result: dict[str, Any] = {"id": listing_id}

    def g(key: str, default: Any = "") -> Any:
        val = info.get(key)
        return default if val is None else val

    result["title"] = g("title")
    result["price"] = g("total_price")
    result["price_unit"] = "萬元"
    unit_price = g("house_unit_price")
    result["unit_price"] = f"{unit_price}萬/坪" if unit_price != "" else ""
    result["addr"] = "".join([g("city"), g("area"), g("road")])
    result["latitude"] = g("latitude")
    result["longitude"] = g("longitude")
    result["社區"] = (info.get("object_data") or {}).get("title", "")
    result["格局"] = f"{g('room', '')}房{g('livingrooms', '')}廳{g('bathrooms', '')}衛" if any(
        info.get(k) is not None for k in ("room", "livingrooms", "bathrooms")
    ) else ""
    house_age = g("house_age")
    result["屋齡"] = f"{house_age}年" if house_age != "" else ""
    total_area = g("total_area_ping")
    result["坪數"] = f"{total_area}坪" if total_area != "" else ""
    result["樓層"] = f"{g('floor')}F/{g('total_floor')}F" if info.get("floor") is not None else ""
    result["管理費"] = g("manage_fee")
    result["法定用途"] = g("usage")
    parking_types = "、".join(info.get("parking_types") or [])
    result["車位"] = parking_types if parking_types else "無"
    # 公設比 = 公設坪數 / 總坪數
    try:
        public_ping = float(info.get("public_area_ping") or 0)
        total_ping = float(info.get("total_area_ping") or 0)
        result["公設比"] = f"{round(public_ping / total_ping * 100)}%" if total_ping else ""
    except (TypeError, ValueError):
        result["公設比"] = ""
    building_ping = g("building_ping")
    result["主建物"] = f"{building_ping}坪" if building_ping != "" else ""
    att_ping = g("att_ping")
    result["附屬建物"] = f"{att_ping}坪" if att_ping != "" else ""
    public_area = g("public_area_ping")
    result["共用部分"] = f"{public_area}坪" if public_area != "" else ""
    land_ping = g("land_ping")
    result["土地坪數"] = f"{land_ping}坪" if land_ping != "" else ""

    contact = info.get("contact_info") or {}
    result["仲介"] = contact.get("name", "")
    company = contact.get("company", "")
    department = contact.get("company_department", "")
    result["仲介公司"] = f"{company}({department})" if company and department else company

    today = date.today()
    result["fetched"] = f"{today.month}/{today.day}/{today.year}"
    result["link"] = f"{DETAIL_BASE}{listing_id}"
    result["採光方向"] = "、".join(
        DIRECTION_MAP.get(d, d) for d in (info.get("direction") or "").split(",") if d
    )
    result["土地使用"] = g("land_use")
    # 房屋類型: 預售 > 新建 > 中古
    if info.get("is_presale"):
        result["房屋類型"] = "預售"
    elif info.get("is_new_sale"):
        result["房屋類型"] = "新建"
    else:
        result["房屋類型"] = "中古"

    return result


@retry(stop=stop_after_attempt(3), wait=wait_random(min=1, max=3), reraise=True)
def get_page(page: ChromiumPage, listing_id: str) -> str:
    """Navigate to a detail page and return its HTML, retrying on failure.

    Args:
        page: DrissionPage page instance.
        listing_id: The hash_sales_id.

    Returns:
        The page HTML.

    Raises:
        NotExistException: If the object has been removed (下架).
    """
    navigate_to_a_page(page, f"{DETAIL_BASE}{listing_id}", wait_selector="", timeout=15)
    wait_passed_cloudflare(page)
    time.sleep(random.random() * 1.5 + 0.5)

    title = page.title or ""
    if "已下架" in title or "不存在" in title or "找不到" in title:
        raise NotExistException(f"{listing_id} removed: {title}")
    return page.html


def get_listing_info(page: ChromiumPage, listing_id: str) -> dict[str, Any]:
    """Extract flattened listing information for a single object.

    Args:
        page: DrissionPage page instance.
        listing_id: The hash_sales_id.

    Returns:
        A flat record dict.
    """
    try:
        html = get_page(page, listing_id)
    except RetryError:
        LOGGER.warning(f"RetryError for listing {listing_id}; parsing whatever is on the page.")
        html = page.html

    info = extract_object_info(html, listing_id)
    if not info:
        LOGGER.warning(f"No salesObjectInfo found for {listing_id}.")
        return {"id": listing_id}
    return flatten_info(info, listing_id)


def main(
    source_path: Optional[str] = "cache/leju_listings.jbl",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    quiet: bool = True,
    use_tqdm: bool = True,
    id_list: Optional[list[str]] = None,
):
    """Main function to fetch leju sale listing information.

    Args:
        source_path: Path to the joblib file containing hash_sales_id values.
        data_path: Path to existing CSV data to merge with (auto-detected if not provided)
        output_path: Path to save the output CSV
        limit: Maximum number of listings to fetch (-1 for all)
        quiet: Whether to run in headless mode
        use_tqdm: Whether to display a tqdm progress bar (useful when running directly in terminal)
        id_list: Listing IDs passed directly (GUI mode); skips loading source_path

    Returns:
        List of fetched records.
    """
    if id_list is None:
        if not source_path or not os.path.exists(source_path):
            print(f"Error: source file not found: {source_path}")
            raise FileNotFoundError(source_path)
        listing_ids = joblib.load(source_path)
    else:
        listing_ids = list(id_list)
        if source_path is None:
            source_path = "cache/leju_listings.jbl"

    output_path, data_path = deal_paths(source_path, output_path, data_path, objective="leju")
    
    existing_records: list[dict[str, Any]] = []
    existing_ids: set[str] = set()

    if os.path.exists(data_path):
        existing_records, existing_ids = load_existing_csv_data(data_path)
        print(f"Loaded {len(existing_ids)} existing records from {data_path}")

    listing_ids = [id_ for id_ in listing_ids if id_ not in existing_ids]
    print(f"After filtering existing: {len(listing_ids)} listings to fetch")

    if limit > 0:
        listing_ids = listing_ids[:limit]

    print(f"Fetching {len(listing_ids)} entries...")

    if not listing_ids:
        print("Nothing to fetch.")
        return existing_records

    page = create_browser(headless=quiet)
    print("Browser initialized.")

    # Warm up on the list page once to pass Cloudflare and set cookies.
    navigate_to_a_page(page, "https://www.leju.com.tw/object_list", wait_selector="", timeout=15)
    wait_passed_cloudflare(page)
    time.sleep(2)

    data: list[dict[str, Any]] = []
    total = len(listing_ids)
    iterator = tqdm(listing_ids, ncols=100) if use_tqdm else listing_ids
    for idx, listing_id in enumerate(iterator, start=1):
        try:
            record = get_listing_info(page, listing_id)
        except NotExistException as e:
            LOGGER.info(f"Skip {e}")
            continue
        except Exception as e:
            LOGGER.error(f"Failed to fetch {listing_id}: {e}")
            continue

        clean_record_strings([record])
        append_record(record, output_path, list(record.keys()))
        data.append(record)
        print(f"Fetch progress: {idx}/{total}")
        LOGGER.info(f"Fetch progress: {idx}/{total}")
        time.sleep(random.random() * 2 + 1)

    page.quit()

    print_sample_records(data, sample_size=3)
    print(f"Done! Total records fetched: {len(data)}")
    return data


if __name__ == "__main__":
    typer.run(main)
