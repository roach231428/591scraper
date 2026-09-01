"""Shared extraction utilities for 591.com.tw scrapers.

This module provides common functions for extracting listing IDs and data
from various 591.com.tw page types (sale, rent, new house).
"""

import json
import re
from typing import Any, Dict, List, Optional


def extract_id_from_href(href: str, pattern: str = "default") -> Optional[str]:
    """Extract listing ID from an href string using common patterns.
    
    Args:
        href: The href attribute value.
        pattern: The pattern to use:
            - "default": Matches /{id}.html or /{id} (for rent)
            - "sale": Matches /detail/{num}/{id}.html (for sale)
            
    Returns:
        The extracted ID or None if not found.
    """
    if not href:
        return None
    
    if pattern == "sale":
        match = re.search(r'/detail/\d+/(\d+)\.html', href)
        if match:
            return match.group(1)
    else:
        match = re.search(r'/(\d+)(?:\.html)?$', href)
        if match:
            return match.group(1)
    
    return None


def extract_ids_from_json_ld(html: str) -> List[str]:
    """Extract listing IDs from JSON-LD structured data in HTML.
    
    Used by new house pages that use JSON-LD for listing data.
    
    Args:
        html: The page HTML content.
        
    Returns:
        List of listing IDs extracted from the JSON-LD data.
    """
    listing_ids: List[str] = []
    
    pattern = r'<script\s+type="application/ld\+json">\s*({.*?})\s*</script>'
    matches = re.findall(pattern, html, re.DOTALL)
    
    for content in matches:
        try:
            content = re.sub(r'<!--\s*', '', content)
            content = re.sub(r'\s*-->', '', content)
            
            data = json.loads(content)
            
            if data.get("@type") == "ItemList":
                items = data.get("itemListElement", [])
                for item in items:
                    product = item.get("item", {})
                    url = product.get("url", "")
                    
                    match = re.search(r'newhouse\.591\.com\.tw/(\d+)', url)
                    if match:
                        listing_ids.append(match.group(1))
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"  Failed to parse JSON-LD: {e}")
            continue
    
    return listing_ids


def extract_data_by_box_title(page: Any, box_title: str) -> Dict[str, str]:
    """Extract key-value data from a detail-house-box by title keyword.
    
    Used by sale listing detail pages to extract structured data.
    
    Args:
        page: DrissionPage page instance.
        box_title: Title keyword to search for (e.g., "房屋資料", "坪數說明").
        
    Returns:
        Dictionary of extracted key-value pairs.
    """
    result: Dict[str, str] = {}
    try:
        all_boxes = page.eles("css:.detail-house-box")
        if not all_boxes:
            return result
        
        house_box = None
        for box in all_boxes:
            h3 = box.ele("css:h3.detail-house-name")
            if h3:
                title_normalized = re.sub(r'\s+', '', h3.text or "")
                if box_title in title_normalized:
                    house_box = box
                    break
        
        if not house_box:
            return result
        
        items = house_box.eles("css:.detail-house-item")
        
        for item in items:
            key_el = item.ele("css:.detail-house-key", timeout=0.1)
            value_el = item.ele("css:.detail-house-value", timeout=0.1)
            if key_el and value_el:
                key = key_el.text.strip().replace("\n", "").replace("\r", "")
                try:
                    span_el = value_el.ele("css:span", timeout=0.1)
                    value = span_el.text.strip() if span_el else value_el.text.strip()
                except Exception:
                    value = value_el.text.strip()
                value = value.replace("\n", "").replace("\r", "")
                result[key] = value
    except Exception as e:
        print(f"Error extracting house data for '{box_title}': {e}")
    
    return result


def extract_list_from_box(page: Any, box_title: str, item_selector: str, 
                          text_key: str = "text") -> str:
    """Extract a comma-separated list of items from a box by title.
    
    Used for extracting living functions, nearby transportation, etc.
    
    Args:
        page: DrissionPage page instance.
        box_title: Title keyword to search for.
        item_selector: CSS selector for each item within the box.
        text_key: Attribute or method to get text from ('text', 'text', etc.).
        
    Returns:
        Comma-separated string of items.
    """
    items_list: List[str] = []
    try:
        all_boxes = page.eles("css:.detail-house-box")
        if not all_boxes:
            return ""
        
        target_box = None
        for box in all_boxes:
            h3 = box.ele("css:h3.detail-house-name")
            if h3:
                title = re.sub(r'\s+', '', h3.text or "")
                if box_title in title:
                    target_box = box
                    break
        
        if not target_box:
            return ""
        
        elements = target_box.eles(f"css:{item_selector}")
        for el in elements:
            text = el.text.strip()
            text = text.split(' ')[0] if text else ""
            if text:
                items_list.append(text)
    except Exception as e:
        print(f"Error extracting list for '{box_title}': {e}")
    
    return "，".join(items_list) if items_list else ""
