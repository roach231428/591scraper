import re
import time
import shutil
import random
import logging
from datetime import date
from typing import Optional, Any

import typer
import joblib
import pandas as pd
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

from utils.post_processing import adjust_price_, auto_marking_, parse_price
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
    df_original: Optional[pd.DataFrame] = None
    if data_path:
        if data_path.endswith(".pd"):
            df_original = pd.read_pickle(data_path)
        else:
            df_original = pd.read_csv(data_path)
        listing_ids = list(set(listing_ids) - set(df_original.id.values.astype("str")))
        print(len(listing_ids))

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
            pass
        print(f"Fetch progress: {idx}/{total}")
        LOGGER.info(f"Fetch progress: {idx}/{total}")
        time.sleep(random.random() * 5)

    df_new = pd.DataFrame(data)
    optional_fields = ("租金含", "車位費", "管理費")
    for field in optional_fields:
        if field not in df_new:
            df_new[field] = None
    df_new = auto_marking_(df_new)
    df_new = adjust_price_(df_new)
    df_new["fetched"] = date.today().isoformat()
    if df_original is not None:
        df_new = pd.concat([df_new, df_original], axis=0).reset_index(drop=True)

    if output_path is None and data_path is None:
        # default output path
        output_path = "cache/df_listings.csv"
    elif output_path is None and data_path:
        output_path = data_path
        shutil.copy(data_path, data_path + ".bak")

    df_new["link"] = "https://rent.591.com.tw/rent-detail-" + df_new["id"].astype("str") + ".html"
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
    print(df_new.drop("desc", axis=1).sample(min(df_new.shape[0], 10)))
    df_new[column_ordering].to_csv(output_path, index=False)
    print("Finished!")

    page.quit()


if __name__ == "__main__":
    typer.run(main)
