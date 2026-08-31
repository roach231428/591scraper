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

from collect_sale_list import create_browser

LOGGER = logging.getLogger(__name__)


class PageLoadError(Exception):
    pass


class NotExistException(Exception):
    pass


def navigate_to_a_page(page: ChromiumPage, url: str):
    """Navigate to a page and wait for content to load."""
    try:
        page.get(url)
    except Exception as e:
        print(f"Failed to navigate to the page: {e}")
        raise e

    # Just wait for page to load with a simple sleep
    # This is more reliable than waiting for specific elements
    time.sleep(random.random() + 1)


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
        page_title = page.title.lower()
        if "不存在" in page.title or "找不到" in page.title or "失效" in page.title:
            raise NotExistException()


def extract_house_data(page: ChromiumPage, box_title: str) -> dict:
    """Extract house data from a detail-house-box by title keyword.

    This function searches all detail-house-box elements and finds the one
    whose title (h3.detail-house-name) contains the given box_title keyword.
    
    Args:
        page: DrissionPage page instance
        box_title: Title keyword to search for (e.g., "房屋資料", "坪數說明")
        
    Returns:
        Dictionary of extracted data
    """
    result = {}
    try:
        # Get all house boxes first (fast operation)
        all_boxes = page.eles("css:.detail-house-box")
        if not all_boxes:
            return result
        
        # Print all box titles for debugging
        box_titles = []
        for i, box in enumerate(all_boxes):
            h3 = box.ele("css:h3.detail-house-name")
            title = h3.text.strip().replace("\n", "") if h3 else "No title"
            box_titles.append(f"{i}:'{title}'")
        LOGGER.info(f"Available boxes: {', '.join(box_titles)}")
        
        # Find the box by title (more reliable than nth-of-type)
        # Note: 591 page may have spaces and newlines in titles (e.g., "房\n屋資料" instead of "房屋資料")
        # So we need to remove all whitespace characters before comparing
        house_box = None
        for box in all_boxes:
            h3 = box.ele("css:h3.detail-house-name")
            if h3:
                # Remove all whitespace (spaces, newlines, etc.) from the title for comparison
                title_normalized = re.sub(r'\s+', '', h3.text or "")
                if box_title in title_normalized:
                    house_box = box
                    break
        
        if not house_box:
            # Only process boxes that match the expected title by name.
            LOGGER.warning(f"Box '{box_title}' not found in any detail-house-box")
            return result
        
        items = house_box.eles("css:.detail-house-item")
        LOGGER.debug(f"Found {len(items)} items in box '{box_title}'")
        
        for item in items:
            key_el = item.ele("css:.detail-house-key", timeout=0.1)
            value_el = item.ele("css:.detail-house-value", timeout=0.1)
            if key_el and value_el:
                key = key_el.text.strip().replace("\n", "").replace("\r", "")
                try:
                    span_el = value_el.ele("css:span", timeout=0.1)
                    value = span_el.text.strip() if span_el else value_el.text.strip()
                except Exception:
                    # If timeout or any error, just use the value_el text directly
                    value = value_el.text.strip()
                value = value.replace("\n", "").replace("\r", "")
                result[key] = value
    except Exception as e:
        LOGGER.warning(f"Error extracting house data for '{box_title}': {e}")
    
    return result


def extract_living_functions(page: ChromiumPage) -> str:
    """Extract living functions (生活機能) from the page.
    
    Returns:
        Comma-separated string of facility names
    """
    functions = []
    try:
        all_boxes = page.eles("css:.detail-house-box")
        if not all_boxes:
            return ""
        
        # Find the box with "生活機能" title
        func_box = None
        for box in all_boxes:
            h3 = box.ele("css:h3.detail-house-name")
            if h3:
                title = re.sub(r'\s+', '', h3.text or "")
                if "生活機能" in title:
                    func_box = box
                    break
        
        if not func_box:
            return ""
        
        items = func_box.eles("css:.detail-house-item")
        for item in items:
            life_el = item.ele("css:.detail-house-life")
            if life_el:
                # Get text and only keep the first part before space
                text = life_el.text.strip()
                # Split by space and take only the first part
                text = text.split(' ')[0] if text else ""
                functions.append(text)
    except Exception as e:
        LOGGER.warning(f"Error extracting living functions: {e}")
    
    return "，".join(functions) if functions else ""


def extract_nearby_transportation(page: ChromiumPage) -> str:
    """Extract nearby transportation (附近交通) from the page.

    Returns:
        Comma-separated string of transportation options
    """
    transportation = []
    try:
        all_boxes = page.eles("css:.detail-house-box")
        if not all_boxes:
            return ""

        # Find the box with "附近交通" title
        trans_box = None
        for box in all_boxes:
            h3 = box.ele("css:h3.detail-house-name")
            if h3:
                title = re.sub(r'\s+', '', h3.text or "")
                if "附近交通" in title:
                    trans_box = box
                    break

        if not trans_box:
            return ""

        items = trans_box.eles("css:.detail-house-item")
        for item in items:
            value_el = item.ele("css:.detail-house-value")
            if value_el:
                text = value_el.text.strip()
                text = text.split(' ')[0] if text else ""
                transportation.append(text)
    except Exception as e:
        LOGGER.warning(f"Error extracting nearby transportation: {e}")
    
    return "，".join(transportation) if transportation else ""


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
    house_data = extract_house_data(page, "房屋資料")
    result.update(house_data)

    # 坪數說明 (主建物, 附屬建物, 共有部分, 總坪數)
    area_data = extract_house_data(page, "坪數說明")
    result.update(area_data)

    # 生活機能
    result["生活機能"] = extract_living_functions(page)

    # 附近交通
    result["附近交通"] = extract_nearby_transportation(page)

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
    headless: bool = False,
):
    """Main function to fetch sale listing information.
    
    Args:
        source_path: Path to the joblib file containing listing IDs
        data_path: Path to existing CSV data to merge with
        output_path: Path to save the output CSV
        limit: Maximum number of listings to fetch (-1 for all)
        headless: Whether to run in headless mode
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

    page = create_browser(headless=headless)

    data = []
    for id_ in tqdm(listing_ids, ncols=100):
        try:
            data.append(get_listing_info(page, id_))
        except NotExistException:
            LOGGER.warning(f"Does not exist: {id_}")
            pass
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
