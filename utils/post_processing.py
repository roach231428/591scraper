import re
from dataclasses import dataclass, field, asdict, replace
from typing import Any


def parse_price(price_str: str) -> int:
    if price_str == "" or "--" in price_str or "無" in price_str:
        return 0
    try:
        # Greedy match the first numbers (including commas)
        return int(re.match(r"^([\d,]+)", price_str).group(1).replace(",", ""))  # pyright: ignore[reportOptionalMemberAccess]
    except AttributeError:
        return 0


def auto_marking(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add 'mark' field to each record. Marks 'x' for social housing or mechanical parking."""
    for record in records:
        mark = ""
        title = record.get("title", "")
        desc = record.get("desc", "")
        provider = record.get("提供設備", "")

        if "社宅" in title or "社會住宅" in title or "社會住宅" in desc:
            mark = "x"
        if "機械車位" in provider:
            mark = "x"
        record["mark"] = mark
    return records


def adjust_price(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calculate price_adjusted for each record based on service fee, management fee, and parking fee."""
    for record in records:
        price = record.get("price", 0)
        poster = record.get("poster", "")
        management_fee_str = record.get("管理費", "")
        parking_fee_str = record.get("車位費", "")

        # Calculate service fee multiplier (1/24 if service fee exists)
        has_service_fee = "收取服務費" in poster
        multiplier = 1 / 24 if has_service_fee else 0
        adjusted = int(price * (multiplier + 1))

        # Add management fee
        adjusted += parse_price(management_fee_str)

        # Add parking fee if "費用另計"
        if "費用另計" in parking_fee_str:
            adjusted += 2500

        record["price_adjusted"] = adjusted
    return records
