"""Fetches detailed information for 591 sale listings from detail pages.

This script reads listing IDs from a joblib file, navigates to each listing's
detail page, extracts information, and saves the results to a CSV file.

The script follows the same pattern as fetch_info.py for rental listings.

Environment Variables:
    X591SaleURL: Used to determine the base URL for detail pages.

Functions:
    main: The main function to execute the sale info fetching process.
"""

import re
import time
import shutil
import random
import logging
import json
from datetime import date
from typing import Optional, Any

import typer
import joblib
import pandas as pd
from tqdm import tqdm
from tenacity import RetryError
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page
from utils.extractor import extract_data_by_box_title, extract_list_from_box

LOGGER = logging.getLogger(__name__)


class PageLoadError(Exception):
    pass


class NotExistException(Exception):
    pass


def parse_price(price_str: str) -> Optional[int]:
    """Parse price string to integer (in 10,000 TWD).
    
    Args:
        price_str: Price string like "1,688" or "1,688 萬元"
        
    Returns:
        Price in 10,000 TWD as integer, or None if parsing fails
    """
    if not price_str:
        return None
    # Remove commas and non-numeric characters except digits
    match = re.search(r'(\d+(?:,\d+)*)', price_str)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def get_page(page: ChromiumPage, listing_id: str):
    """Navigate to a sale listing detail page."""
    navigate_to_a_page(page, f"https://sale.591.com.tw/home/house/detail/2/{listing_id}.html".strip())
    
    # Check if the listing exists by looking for error indicators
    # Use a more specific selector that matches the actual page structure
    title_el = page.ele("css:h1.detail-title-box span.detail-title-text", timeout=3)
    if not title_el:
        # If title not found, check for error indicators in the page title
        if "不存在" in page.title or "找不到" in page.title or "失效" in page.title:
            raise NotExistException()


def get_listing_info(page: ChromiumPage, listing_id: str) -> dict:
    """Extract listing information from a sale detail page.
    
    Args:
        page: DrissionPage page instance
        listing_id: The listing ID
        
    Returns:
        Dictionary containing all extracted information
    """
    try:
        get_page(page, listing_id)
    except RetryError:
        LOGGER.warning(f"RetryError encountered for listing {listing_id}... Trying to parse whatever is on the page.")

    result: dict[str, Any] = {"id": listing_id}

    # 標題
    title_el = page.ele("css:h1.detail-title-box span.detail-title-text")
    result["title"] = title_el.text.strip() if title_el else ""

    # 價格
    price_el = page.ele("css:.info-price-text")
    result["price"] = parse_price(price_el.text if price_el else "")
    
    price_unit_el = page.ele("css:.info-price-unit")
    result["price_unit"] = price_unit_el.text.strip() if price_unit_el else ""
    
    unit_price_el = page.ele("css:.per-price-text")
    result["unit_price"] = unit_price_el.text.strip() if unit_price_el else ""

    try:
        json_ld_text = page.run_js("""
            const el = document.getElementById('sale-detail-structured-data');
            return el ? el.textContent : '';
        """)
        if json_ld_text:
            json_data = json.loads(json_ld_text)
            for item in json_data.get("@graph", []):
                address = item.get("address", {})
                if address:
                    result["addr"] = address.get("streetAddress", "")
                    geo = item.get("geo", {})
                    result["latitude"] = geo.get("latitude")
                    result["longitude"] = geo.get("longitude")
                    break
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        LOGGER.warning(f"Failed to parse JSON-LD address: {e}")
        result["addr"] = ""

    # 社區
    community_el = page.ele("css:.info-addr-value.community-link a")
    result["社區"] = community_el.text.strip() if community_el else ""

    # 規格資訊 (格局, 屋齡, 坪數, 樓層)
    floor_keys = page.eles("css:.info-floor-key-2")
    if len(floor_keys) >= 1:
        result["格局"] = floor_keys[0].text.strip()
    if len(floor_keys) >= 2:
        result["屋齡"] = floor_keys[1].text.strip()

    area_el = page.ele("css:.info-floor-value-text")
    result["坪數"] = area_el.text.strip() if area_el else ""

    floor_el = page.ele("css:.info-addr-value-text.is-floor")
    result["樓層"] = floor_el.text.strip() if floor_el else ""

    # 房屋資料 (現況, 型態, 裝潢程度, 管理費, 車位, 公設比等)
    house_data = extract_data_by_box_title(page, "房屋資料")
    result.update(house_data)

    # 坪數說明 (主建物, 附屬建物, 共有部分, 總坪數)
    area_data = extract_data_by_box_title(page, "坪數說明")
    result.update(area_data)

    # 生活機能
    result["生活機能"] = extract_list_from_box(page, "生活機能", ".detail-house-life")

    # 附近交通
    result["附近交通"] = extract_list_from_box(page, "附近交通", ".detail-house-value")

    # 仲介資訊
    agent_el = page.ele("css:.pc-agent-name")
    result["仲介"] = agent_el.text.strip() if agent_el else ""
    
    company_el = page.ele("css:.pc-agent-company span")
    result["仲介公司"] = company_el.text.strip() if company_el else ""

    # 有效期
    info_spans = page.eles("css:.detail-info-span")
    if len(info_spans) >= 1:
        result["有效期"] = info_spans[-1].text.strip() if info_spans[-1] else ""

    return result


def main(
    source_path: str = "cache/sale_listings.jbl",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    quiet: bool = False,
    use_tqdm: bool = True,
):
    """Main function to fetch sale listing information.
    
    Args:
        source_path: Path to the joblib file containing listing IDs
        data_path: Path to existing CSV data to merge with
        output_path: Path to save the output CSV
        limit: Maximum number of listings to fetch (-1 for all)
        quiet: Whether to run in headless mode
        use_tqdm: Whether to display a tqdm progress bar (useful when running directly in terminal)
    """
    # joblib is used here to maintain compatibility with the collect_sale_list.py output format
    listing_ids = joblib.load(source_path)
    df_original: Optional[pd.DataFrame] = None
    if data_path:
        if data_path.endswith(".pd"):
            df_original = pd.read_pickle(data_path)
        else:
            df_original = pd.read_csv(data_path)
        listing_ids = list(set(listing_ids) - set(df_original.id.values.astype("str")))
        print(f"After filtering existing: {len(listing_ids)} listings to fetch")

    if limit > 0:
        listing_ids = listing_ids[:limit]

    print(f"Collecting {len(listing_ids)} entries...")

    page = create_browser(headless=quiet)

    data = []
    total = len(listing_ids)
    iterator = tqdm(listing_ids, ncols=100) if use_tqdm else listing_ids
    for idx, id_ in enumerate(iterator, start=1):
        try:
            data.append(get_listing_info(page, id_))
        except NotExistException:
            LOGGER.warning(f"Does not exist: {id_}")
            # continue without adding
        print(f"Fetch progress: {idx}/{total}")
        LOGGER.info(f"Fetch progress: {idx}/{total}")
        time.sleep(random.random() + 1)

    df_new = pd.DataFrame(data)
    df_new["fetched"] = date.today().isoformat()
    
    # Ensure all columns in column_ordering exist (even if empty) to avoid KeyError when selecting columns
    # This must be done BEFORE defining column_ordering
    expected_columns = [
        "title",
        "price",
        "price_unit",
        "unit_price",
        "link",
        "addr",
        "latitude",
        "longitude",
        "社區",
        "格局",
        "屋齡",
        "樓層",
        "坪數",
        "主建物",
        "附屬建物",
        "共用部分",
        "公設比",
        "管理費",
        "生活機能",
        "附近交通",
        "仲介",
        "仲介公司",
        "fetched",
    ]
    for col in expected_columns:
        if col not in df_new.columns:
            df_new[col] = ""
    
    if df_original is not None:
        df_new = pd.concat([df_new, df_original], axis=0).reset_index(drop=True)

    if output_path is None and data_path is None:
        # default output path
        output_path = "cache/df_sale_listings.csv"
    elif output_path is None and data_path:
        output_path = data_path
        shutil.copy(data_path, data_path + ".bak")

    df_new["link"] = "https://sale.591.com.tw/home/house/detail/2/" + df_new["id"].astype("str") + ".html"

    df_new.columns = df_new.columns.str.replace("\n", "").str.replace("\r", "")

    for col in df_new.select_dtypes(include="object").columns:
        df_new[col] = df_new[col].astype(str).str.replace("\n", "").str.replace("\r", "")
    
    # Define fixed column order for output
    column_ordering = expected_columns.copy()
    
    print(df_new.sample(min(df_new.shape[0], 10)))
    df_new[column_ordering].to_csv(output_path, index=False, encoding='utf-8-sig')
    print("Finished!")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
