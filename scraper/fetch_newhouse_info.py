"""Fetches detailed information for 591 new house (新建案) listings from detail pages.

This script reads listing IDs from a joblib file, navigates to each listing's
detail page (https://newhouse.591.com.tw/{id}), extracts information, and saves
the results to a CSV file.

The script follows the same pattern as fetch_sale_info.py / fetch_rent_info.py.

Functions:
    main: The main function to execute the new house info fetching process.
"""

import os
import re
import time
import random
import logging
import json
from datetime import date
from typing import Optional, Any

import typer
import joblib
from tqdm import tqdm
from tenacity import RetryError
from DrissionPage import ChromiumPage

from utils.browser import create_browser, navigate_to_a_page
from utils.persistence import load_existing_csv_data, save_records, clean_record_strings, deal_paths, print_sample_records

LOGGER = logging.getLogger(__name__)


class PageLoadError(Exception):
    pass


class NotExistException(Exception):
    pass


def parse_price(price_str: str) -> Optional[float]:
    """Parse price string to float.

    Handles strings like "78~83", "78.5", "1,688 萬元", "價格待定".

    Args:
        price_str: Price string.

    Returns:
        Price as float, or None if parsing fails.
    """
    if not price_str:
        return None
    match = re.search(r"(\d+(?:\.\d+)?(?:,\d+)*)", price_str)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def get_page(page: ChromiumPage, listing_id: str):
    """Navigate to a new house listing detail page."""
    navigate_to_a_page(
        page,
        f"https://newhouse.591.com.tw/{listing_id}".strip(),
        wait_selector="h1.build-name",
    )

    # A delisted new-house ID gets redirected to the real-price site
    # (market.591.com.tw). Treat that as "does not exist" and skip it.
    if "newhouse.591.com.tw" not in page.url:
        raise NotExistException()

    # Check if the listing exists by looking for error indicators
    title_el = page.ele("css:h1.build-name", timeout=0.01)
    if not title_el:
        if "不存在" in page.title or "找不到" in page.title or "失效" in page.title:
            raise NotExistException()


def _clean_text(text: str) -> str:
    """Normalize whitespace in extracted text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_ld(page: ChromiumPage) -> dict:
    """Extract the detail-structured-data JSON-LD from the page.

    Returns:
        Parsed JSON-LD dictionary, or an empty dict on failure.
    """
    try:
        json_ld_text = page.run_js(
            """
            const el = document.querySelector('script[data-hid="detail-structured-data"]');
            return el ? el.textContent : '';
            """
        )
        if json_ld_text:
            return json.loads(json_ld_text)
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        LOGGER.warning(f"Failed to parse JSON-LD: {e}")
    return {}


def _extract_intro_info(page: ChromiumPage) -> dict:
    """Extract the intro-info block (總價/車位/格局/坪數/完工/建設/生活圈/基地地址).

    Returns:
        Dictionary of extracted key-value pairs.
    """
    result: dict[str, str] = {}
    try:
        # DrissionPage does not support comma-separated locators, so query
        # <p> and <div> info items separately.
        items = page.eles("css:.intro-info p.info-item", timeout=0.01) + page.eles(
            "css:.intro-info div.info-item", timeout=0.01
        )
        for item in items:
            label_el = item.ele("css:span.label", timeout=0.01)
            if not label_el:
                continue
            key = _clean_text(label_el.text)
            if not key:
                continue

            # 基地地址 uses .address-right instead of .text
            value_el = item.ele("css:span.text", timeout=0.01)
            if value_el:
                value = _clean_text(value_el.text)
                # 生活圈 link text ends with a trailing ">" arrow
                value = value.rstrip(">").strip()
            else:
                addr_el = item.ele("css:span.address-right", timeout=0.01)
                if addr_el:
                    # Remove trailing "查看地圖>" link text
                    value = _clean_text(addr_el.text).replace("查看地圖>", "").strip()
                else:
                    value = ""
            result[key] = value
    except Exception as e:
        LOGGER.warning(f"Error extracting intro info: {e}")
    return result


def _extract_plan_data(page: ChromiumPage) -> dict:
    """Extract 社區規劃 data (建築規劃 + 建商資料) from the page.

    Only the PC list (.plan-list-pc) and the 建商資料 (.data-list) are read to
    avoid duplicates from the mobile-only lists.

    Returns:
        Dictionary of extracted key-value pairs.
    """
    result: dict[str, str] = {}
    try:
        sections = [
            ("css:ul.plan-list.plan-list-pc", "建築規劃"),
            ("css:ul.data-list", "建商資料"),
        ]
        for selector, section_name in sections:
            lists = page.eles(selector, timeout=0.01)
            for lst in lists:
                items = lst.eles("css:li.list-item", timeout=0.01)
                for item in items:
                    key_el = item.ele("css:h4", timeout=0.01)
                    value_el = item.ele("css:p", timeout=0.01)
                    if not key_el or not value_el:
                        continue
                    key = _clean_text(key_el.text)
                    if not key:
                        continue
                    # The value <p> may contain a hidden tooltip <i> whose text
                    # leaks into .text after a run_js call. Read only the first
                    # text node via JS to get the clean value.
                    try:
                        value = value_el.run_js(
                            "return this.firstChild ? this.firstChild.textContent : '';"
                        )
                    except Exception:
                        value = None
                    if value is None:
                        value = value_el.text
                    value = _clean_text(value)
                    result[key] = value
    except Exception as e:
        LOGGER.warning(f"Error extracting plan data ({section_name}): {e}")
    return result


def _extract_tags(page: ChromiumPage) -> str:
    """Extract build tags (在售/預售屋/住宅大樓/...)."""
    try:
        tags = page.eles("css:.build-tag span.tag", timeout=0.01)
        texts = [_clean_text(t.text) for t in tags if t.text]
        return "，".join(t for t in texts if t)
    except Exception:
        return ""


def _extract_latest_updates(page: ChromiumPage) -> str:
    """Extract 最新動態 timeline entries as a joined string."""
    try:
        items = page.eles("css:ul.dynamic-detail li", timeout=0.01)
        entries: list[str] = []
        for item in items:
            date_el = item.ele("css:.detail-date", timeout=0.01)
            text_el = item.ele("css:p.detail-text", timeout=0.01)
            if not text_el:
                continue
            date_text = _clean_text(date_el.text) if date_el else ""
            entries.append(f"{date_text} {_clean_text(text_el.text)}".strip())
        return " | ".join(entries)
    except Exception:
        return ""


def _extract_deals(page: ChromiumPage) -> str:
    """Extract 成交行情 (recent deals) as a joined string."""
    try:
        cards = page.eles("css:li.deal-card", timeout=0.01)
        entries: list[str] = []
        for card in cards:
            date_el = card.ele("css:.deal-date", timeout=0.01)
            id_el = card.ele("css:h3.property-id", timeout=0.01)
            detail_el = card.ele("css:p.property-details", timeout=0.01)
            unit_price_el = card.ele("css:span.unit-price", timeout=0.01)
            area_el = card.ele("css:span.area-text", timeout=0.01)
            total_el = card.ele("css:span.total-price", timeout=0.01)

            parts = [
                _clean_text(date_el.text) if date_el else "",
                _clean_text(id_el.text) if id_el else "",
                _clean_text(detail_el.text) if detail_el else "",
                _clean_text(unit_price_el.text) if unit_price_el else "",
                _clean_text(area_el.text) if area_el else "",
                _clean_text(total_el.text) if total_el else "",
            ]
            entry = " ".join(p for p in parts if p)
            if entry:
                entries.append(entry)
        return " | ".join(entries)
    except Exception:
        return ""


def get_listing_info(page: ChromiumPage, listing_id: str) -> dict:
    """Extract listing information from a new house detail page.

    Args:
        page: DrissionPage page instance
        listing_id: The listing ID

    Returns:
        Dictionary containing all extracted information
    """
    try:
        get_page(page, listing_id)
    except RetryError:
        LOGGER.warning(
            f"RetryError encountered for listing {listing_id}... "
            "Trying to parse whatever is on the page."
        )

    result: dict[str, Any] = {"id": listing_id}

    # 建案名稱
    title_el = page.ele("css:h1.build-name", timeout=0.01)
    result["title"] = _clean_text(title_el.text) if title_el else ""

    # 建案標籤 (在售/預售屋/...)
    result["標籤"] = _extract_tags(page)

    # 價格 (單價) — .build-price .price, e.g. "78~83" or "價格待定"
    price_el = page.ele("css:.build-price span.price", timeout=0.01)
    price_text = _clean_text(price_el.text) if price_el else ""
    result["price"] = price_text
    result["price_value"] = parse_price(price_text)

    price_unit_el = page.ele("css:.build-price span.unit", timeout=0.01)
    result["price_unit"] = _clean_text(price_unit_el.text) if price_unit_el else ""

    # 區域比價 (高於區域x%)
    compare_el = page.ele("css:.build-price a", timeout=0.01)
    result["區域比價"] = _clean_text(compare_el.text).replace(">", "").strip() if compare_el else ""

    # JSON-LD 結構化資料
    json_data = _extract_json_ld(page)
    result["addr"] = ""
    result["latitude"] = None
    result["longitude"] = None
    result["建設"] = ""
    result["電話"] = ""
    result["描述"] = ""
    try:
        for item in json_data.get("@graph", []):
            itype = item.get("@type")
            if itype == "ApartmentComplex":
                address = item.get("address", {})
                if address:
                    result["addr"] = address.get("streetAddress", "")
                geo = item.get("geo", {})
                result["latitude"] = geo.get("latitude")
                result["longitude"] = geo.get("longitude")
                result["電話"] = item.get("telephone", "")
                result["描述"] = item.get("description", "")
            elif itype == "Organization" and "#builder" in str(item.get("@id", "")):
                result["建設"] = item.get("name", "")
    except Exception as e:
        LOGGER.warning(f"Failed to parse JSON-LD fields: {e}")

    # intro-info 區塊 (總價/車位/格局/坪數/完工/建設/生活圈/基地地址)
    intro = _extract_intro_info(page)
    result["總價"] = intro.get("總價", "")
    result["車位"] = intro.get("車位", "")
    result["格局"] = intro.get("格局", "")
    result["坪數"] = intro.get("坪數", "")
    result["完工"] = intro.get("完工", "")
    result["生活圈"] = intro.get("生活圈", "")
    # 基地地址 from intro-info is more precise; fall back to JSON-LD
    if intro.get("基地地址"):
        result["addr"] = intro["基地地址"]
    # 建設 from intro-info takes precedence over JSON-LD builder name
    if intro.get("建設"):
        result["建設"] = intro["建設"]

    # 社區規劃 (建築規劃 + 建商資料)
    plan = _extract_plan_data(page)
    result["公設比"] = plan.get("公設比", "")
    result["基地面積"] = plan.get("基地面積", "")
    result["建蔽率"] = plan.get("建蔽率", "")
    result["管理費用"] = plan.get("管理費用", "")
    result["車位配比"] = plan.get("車位配比", "")
    result["棟戶規劃"] = plan.get("棟戶規劃", "")
    result["車位規劃"] = plan.get("車位規劃", "")
    result["樓層規劃"] = plan.get("樓層規劃", "")
    result["充電設備"] = plan.get("充電設備", "")
    result["投資建設"] = plan.get("投資建設", "")
    result["營造公司"] = plan.get("營造公司", "")
    result["使用執照"] = plan.get("使用執照", "")
    result["建造執照"] = plan.get("建造執照", "")
    result["企劃銷售"] = plan.get("企劃銷售", "")
    result["建築設計"] = plan.get("建築設計", "")

    # 最新動態
    result["最新動態"] = _extract_latest_updates(page)

    # 成交行情
    result["成交行情"] = _extract_deals(page)

    # 諮詢電話 (contact phone)
    phone_el = page.ele("css:.call-phone strong", timeout=0.01)
    result["諮詢電話"] = _clean_text(phone_el.text) if phone_el else result.get("電話", "")

    return result


def main(
    source_path: str = "cache/newhouse_listings.jbl",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    quiet: bool = False,
    use_tqdm: bool = True,
):
    """Main function to fetch new house listing information.
    
    Args:
        source_path: Path to the joblib file containing listing IDs
        data_path: Path to existing CSV data to merge with (auto-detected if not provided)
        output_path: Path to save the output CSV
        limit: Maximum number of listings to fetch (-1 for all)
        quiet: Whether to run in headless mode
        use_tqdm: Whether to display a tqdm progress bar (useful when running directly in terminal)
    """
    # joblib is used here to maintain compatibility with the collect_newhouse_list.py output format
    listing_ids = joblib.load(source_path)

    output_path, data_path = deal_paths(source_path, output_path, data_path, objective="newhouse")
    
    existing_records: list[dict[str, Any]] = []
    existing_ids: set[str] = set()

    if os.path.exists(data_path):
        existing_records, existing_ids = load_existing_csv_data(data_path)
        print(f"Loaded {len(existing_ids)} existing records from {data_path}")
    
    listing_ids = [id_ for id_ in listing_ids if id_ not in existing_ids]
    print(f"After filtering existing: {len(listing_ids)} listings to fetch")
    
    if limit > 0:
        listing_ids = listing_ids[:limit]
    
    print(f"Collecting {len(listing_ids)} entries...")
    
    # Sequential mode
    page = create_browser(headless=quiet)
    data: list[dict[str, Any]] = []
    total = len(listing_ids)
    iterator = tqdm(listing_ids, ncols=100) if use_tqdm else listing_ids
    for idx, id_ in enumerate(iterator, start=1):
        try:
            data.append(get_listing_info(page, id_))
        except NotExistException:
            LOGGER.warning(f"Does not exist: {id_}")
        print(f"Fetch progress: {idx}/{total}")
        LOGGER.info(f"Fetch progress: {idx}/{total}")
        time.sleep(random.random() + 1)
    page.quit()
    
    # Add fetched date
    for record in data:
        record["fetched"] = date.today().isoformat()

    # Ensure all expected columns exist
    expected_columns = [
        "title",
        "標籤",
        "price",
        "price_value",
        "price_unit",
        "區域比價",
        "link",
        "addr",
        "latitude",
        "longitude",
        "總價",
        "車位",
        "格局",
        "坪數",
        "完工",
        "建設",
        "生活圈",
        "公設比",
        "基地面積",
        "建蔽率",
        "管理費用",
        "車位配比",
        "棟戶規劃",
        "車位規劃",
        "樓層規劃",
        "充電設備",
        "投資建設",
        "營造公司",
        "使用執照",
        "建造執照",
        "企劃銷售",
        "建築設計",
        "最新動態",
        "成交行情",
        "電話",
        "諮詢電話",
        "描述",
        "fetched",
    ]
    for record in data:
        for col in expected_columns:
            if col not in record:
                record[col] = ""

    # Merge with existing records
    if existing_records:
        data = existing_records + data

    # Add link column
    for record in data:
        record["link"] = "https://newhouse.591.com.tw/" + str(record.get("id", ""))

    clean_record_strings(data)
    print_sample_records(data, sample_size=10, include_keys=set(expected_columns))

    # Save to CSV
    save_records(data, output_path)
    print("Finished!")


if __name__ == "__main__":
    typer.run(main)
