"""Utility functions for persistent storage operations.

This module provides shared functions for loading and saving data between
joblib (.jbl) and CSV files, used across all scraper collect/fetch scripts.
"""

import os
import csv
from typing import Any, Dict, List, Optional, Set, Tuple

import joblib


def load_existing_ids(output_path: str) -> Set[str]:
    """Load existing IDs from the output joblib file if it exists.
    
    Args:
        output_path: Path to the joblib file.
        
    Returns:
        Set of existing IDs, or empty set if file doesn't exist.
    """
    if os.path.exists(output_path):
        try:
            existing_ids = joblib.load(output_path)
            return set(existing_ids)
        except Exception as e:
            print(f"Warning: Failed to load existing file {output_path}: {e}")
            return set()
    return set()


def load_existing_csv_data(data_path: str) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Load existing CSV data and return (records, existing_ids).
    
    Args:
        data_path: Path to the CSV file.
        
    Returns:
        Tuple of (records list, existing_ids set).
    """
    records: List[Dict[str, Any]] = []
    existing_ids: Set[str] = set()

    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
                existing_ids.add(row.get("id", ""))

    return records, existing_ids


def auto_detect_csv_path(source_path: str) -> str:
    """Auto-detect CSV data path from source joblib path.
    
    Converts paths like:
    - cache/sale_listings.jbl -> cache/sale_listings.csv
    - cache/listings.jbl -> cache/listings.csv
    - cache/newhouse_listings.jbl -> cache/newhouse_listings.csv
    
    Args:
        source_path: Path to the joblib file.
        
    Returns:
        Auto-detected CSV file path.
    """
    base, _ = os.path.splitext(source_path)
    return base + ".csv"


def save_records(records: List[Dict[str, Any]], output_path: str) -> None:
    """Save records to CSV file.
    
    Args:
        records: List of record dictionaries to save.
        output_path: Path to save the CSV file.
    """
    if not records:
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            pass
        return

    # Determine all fields from records
    fieldnames: List[str] = []
    seen: Set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def clean_record_strings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean all string fields in records by removing newline characters.
    
    Args:
        records: List of record dictionaries to clean.
        
    Returns:
        List of cleaned record dictionaries (modified in place).
    """
    for record in records:
        for key, value in record.items():
            if isinstance(value, str):
                record[key] = value.replace("\n", "").replace("\r", "")
    return records


def print_sample_records(records: List[Dict[str, Any]], sample_size: int = 10,
                         include_keys: Optional[Set[str]] = None,
                         exclude_keys: Optional[Set[str]] = None) -> None:
    """Print sample records from the data.
    
    Args:
        records: List of record dictionaries to print.
        sample_size: Number of sample records to display (default: 10).
        include_keys: If provided, only print these keys.
        exclude_keys: If provided, exclude these keys from output.
    """
    actual_size = min(len(records), sample_size)
    if actual_size == 0:
        return
    
    print("Sample records:")
    for record in records[:actual_size]:
        if include_keys is not None:
            print({k: v for k, v in record.items() if k in include_keys})
        elif exclude_keys is not None:
            print({k: v for k, v in record.items() if k not in exclude_keys})
        else:
            print(record)


def deal_paths(source_path: str, output_path: str, data_path: str, objective: str = "rent") -> str:
    if output_path is None and data_path is None:
        # default output path
        output_path_new = f"cache/df_{objective}_listings.csv"
    elif output_path is None and data_path:
        output_path_new = data_path
        shutil.copy(data_path, data_path + ".bak")
    else:
        output_path_new = output_path

    if data_path is None:
        if output_path:
            data_path_new = output_path
        else:
            base, _ = os.path.splitext(source_path)
            data_path_new = base.replace("_listings", "_listings") + ".csv"
    else:
        data_path_new = data_path
    return output_path_new, data_path_new
