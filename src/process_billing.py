"""
Billing Tracker Processor

Extracts funding tranches and billing milestones from Excel files.
Outputs structured JSON for cash flow analysis.

Features:
- Dynamic header row detection (handles variable whitespace at top of sheets)
- Regex-based column matching (handles column name variations)
- Robust extraction of billing data

Usage:
    python -m src.process_billing
"""

import pandas as pd
import json
import sys
import re
import logging
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import round_monetary, normalize_month
except ImportError:
    def round_monetary(value):
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return 0.0
    
    def normalize_month(date_string):
        return None

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def normalize_billing_date(date_value, reference_months=None):
    """
    Normalize a billing date to YYYY-MM-DD format with smart year inference.
    
    Handles ambiguous dates like "Jan-25" which could mean 2025 or 2026
    by checking against reference months from the UC budget.
    
    Args:
        date_value: Raw date value from Excel (could be datetime, string, etc.)
        reference_months: List of months from UC data (e.g., ['2025-11', '2025-12', '2026-01'])
                         Used to infer correct year for ambiguous dates.
    
    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    from datetime import datetime
    
    if pd.isna(date_value):
        return ""
    
    parsed_month = None
    parsed_year = None
    
    # Check if it's a pandas Timestamp or datetime object
    if hasattr(date_value, 'year') and hasattr(date_value, 'month'):
        parsed_year = date_value.year
        parsed_month = date_value.month
    else:
        # It's a string - try to parse it
        date_str = str(date_value).strip()
        
        # Try various string patterns
        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: (int(m.group(1)), int(m.group(2)))),
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: (int(m.group(3)), int(m.group(1)))),
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: (int(m.group(3)), int(m.group(2)))),
        ]
        
        for pattern, extractor in patterns:
            match = re.match(pattern, date_str)
            if match:
                parsed_year, parsed_month = extractor(match)
                break
        
        # Try month name patterns if not found yet
        if parsed_year is None:
            month_names = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            # Pattern: "Jan-25", "Jan 25", "January 2025", etc.
            month_pattern = r'([a-zA-Z]+)[\s\-/]*(\d{2,4})'
            match = re.search(month_pattern, date_str, re.IGNORECASE)
            if match:
                month_text = match.group(1).lower()[:3]
                year_text = match.group(2)
                
                if month_text in month_names:
                    parsed_month = month_names[month_text]
                    if len(year_text) == 2:
                        parsed_year = 2000 + int(year_text)
                    else:
                        parsed_year = int(year_text)
    
    # If we have a parsed date, check if year needs adjustment
    if parsed_month is not None and parsed_year is not None:
        original_year = parsed_year
        
        # Smart year inference using reference months
        if reference_months and len(reference_months) >= 2:
            # Build the candidate month key
            candidate_month_key = f"{parsed_year:04d}-{parsed_month:02d}"
            
            # Check if this month exists in reference months
            if candidate_month_key not in reference_months:
                # Try the next year
                next_year_key = f"{parsed_year + 1:04d}-{parsed_month:02d}"
                if next_year_key in reference_months:
                    parsed_year = parsed_year + 1
                    logging.info(f"  📅 Date correction: {original_year}-{parsed_month:02d} → {parsed_year}-{parsed_month:02d} (matched to budget period)")
        
        return f"{parsed_year:04d}-{parsed_month:02d}-01 00:00:00"
    
    # Fallback: return original string
    return str(date_value).strip()


# ============================================================================
# COLUMN MATCHING PATTERNS (regex-based for flexibility)
# ============================================================================

# These patterns match column names with varying whitespace and slight naming differences
COLUMN_PATTERNS = {
    'milestone': [
        r'payment\s*milestone.*description',
        r'milestone.*description',
        r'payment\s*milestone',
        r'milestone',
    ],
    'billing_value': [
        r'billing\s*value',
        r'billing\s*amount',
        r'invoice\s*value',
        r'amount',
    ],
    'expected_date': [
        r'expected\s*date.*billing',
        r'expected\s*date.*month.*billing',
        r'expected\s*billing\s*date',
        r'billing\s*date',
    ],
    'timeline': [
        r'type\s*of\s*payment',
        r'payment\s*type',
        r'timeline',
        r'installment',
    ],
}

# Key columns that MUST exist for valid header detection
REQUIRED_COLUMN_PATTERNS = ['billing_value']


def find_column_by_pattern(columns, pattern_list):
    """
    Find a column name that matches any of the given regex patterns.
    
    Args:
        columns: List of column names from DataFrame
        pattern_list: List of regex patterns to try (in order of preference)
        
    Returns:
        Matching column name or None
    """
    for pattern in pattern_list:
        regex = re.compile(pattern, re.IGNORECASE)
        for col in columns:
            col_str = str(col).strip()
            if regex.search(col_str):
                return col
    return None


def detect_header_row(excel_file, sheet_name='Sheet1', max_rows_to_check=10):
    """
    Dynamically detect the header row by searching for required column names.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Sheet name to process
        max_rows_to_check: Maximum number of rows to search for headers
        
    Returns:
        Tuple of (header_row_index, column_mapping) or (None, None) if not found
    """
    logging.info(f"Searching for header row in first {max_rows_to_check} rows...")
    
    # Read without headers to inspect raw data
    df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=max_rows_to_check)
    
    for row_idx in range(len(df_raw)):
        # Get values from this row as potential column names
        potential_headers = df_raw.iloc[row_idx].astype(str).tolist()
        
        # Try to find required columns in this row
        column_mapping = {}
        all_required_found = True
        
        for col_type, patterns in COLUMN_PATTERNS.items():
            matched_col = find_column_by_pattern(potential_headers, patterns)
            if matched_col:
                # Find the actual column index
                col_index = potential_headers.index(matched_col)
                column_mapping[col_type] = {
                    'name': matched_col,
                    'index': col_index
                }
            elif col_type in REQUIRED_COLUMN_PATTERNS:
                all_required_found = False
                break
        
        # Check if we found the required columns
        if all_required_found and 'billing_value' in column_mapping:
            logging.info(f"✓ Found header row at index {row_idx}")
            logging.info(f"  Column mapping: {column_mapping}")
            return row_idx, column_mapping
    
    logging.warning("Could not detect header row automatically")
    return None, None


def process_billing_file(excel_file, sheet_name='Sheet1', header_row=None, reference_months=None):
    """
    Process a billing tracker Excel file.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Sheet name to process
        header_row: Row index where headers are located (0-indexed).
                    If None, will auto-detect by searching for column names.
        reference_months: List of month keys from UC data (e.g., ['2025-11', '2026-01'])
                         Used for smart date inference when dates are ambiguous.
        
    Returns:
        Dictionary containing billing data
    """
    excel_file = Path(excel_file)
    logging.info(f"Processing billing file: {excel_file}")
    
    # Auto-detect header row if not specified
    if header_row is None:
        detected_row, column_mapping = detect_header_row(excel_file, sheet_name)
        if detected_row is not None:
            header_row = detected_row
        else:
            # Fallback: try common header positions
            logging.warning("Auto-detection failed, trying common header positions...")
            for try_row in [0, 1, 2, 3]:
                detected_row, column_mapping = detect_header_row(
                    excel_file, sheet_name, max_rows_to_check=try_row + 1
                )
                if detected_row is not None:
                    header_row = detected_row
                    break
            
            if header_row is None:
                header_row = 0  # Last resort fallback
                logging.warning(f"Using fallback header_row={header_row}")
    else:
        # If header_row is specified, still detect column mapping
        df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=header_row + 1)
        potential_headers = df_raw.iloc[header_row].astype(str).tolist()
        column_mapping = {}
        for col_type, patterns in COLUMN_PATTERNS.items():
            matched_col = find_column_by_pattern(potential_headers, patterns)
            if matched_col:
                col_index = potential_headers.index(matched_col)
                column_mapping[col_type] = {
                    'name': matched_col,
                    'index': col_index
                }
    
    logging.info(f"Using header_row={header_row}")
    
    # Load the sheet with headers at detected/specified row
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
    
    logging.info(f"Loaded {len(df)} rows from Excel")
    logging.info(f"Columns found: {df.columns.tolist()}")
    
    # Find columns using patterns (more robust than exact matching)
    col_milestone = find_column_by_pattern(df.columns.tolist(), COLUMN_PATTERNS['milestone'])
    col_billing_value = find_column_by_pattern(df.columns.tolist(), COLUMN_PATTERNS['billing_value'])
    col_expected_date = find_column_by_pattern(df.columns.tolist(), COLUMN_PATTERNS['expected_date'])
    col_timeline = find_column_by_pattern(df.columns.tolist(), COLUMN_PATTERNS['timeline'])
    
    logging.info(f"Column mapping:")
    logging.info(f"  Milestone:     {col_milestone}")
    logging.info(f"  Billing Value: {col_billing_value}")
    logging.info(f"  Expected Date: {col_expected_date}")
    logging.info(f"  Timeline:      {col_timeline}")
    
    # Check if we have the required billing value column
    if col_billing_value is None:
        logging.error("Could not find 'Billing Value' column!")
        logging.error(f"Available columns: {df.columns.tolist()}")
        return {
            "total_billing_value": 0.0,
            "tranches": [],
            "processing_metadata": {
                "source_file": excel_file.name,
                "sheet_name": sheet_name,
                "error": "Could not find Billing Value column"
            }
        }
    
    # Initialize output structure
    output_data = {
        "total_billing_value": 0.0,
        "tranches": [],
        "processing_metadata": {
            "source_file": excel_file.name,
            "sheet_name": sheet_name,
            "header_row": header_row,
            "columns_detected": {
                "milestone": col_milestone,
                "billing_value": col_billing_value,
                "expected_date": col_expected_date,
                "timeline": col_timeline
            }
        }
    }
    
    # Process each row
    for idx, row in df.iterrows():
        # Get billing value
        billing_value = row.get(col_billing_value) if col_billing_value else None
        
        # Skip if billing value is empty or NaN
        if pd.isna(billing_value):
            continue
        
        # Try to convert to float
        try:
            billing_value_float = float(billing_value)
        except (ValueError, TypeError):
            logging.debug(f"Row {idx}: Could not convert billing value '{billing_value}' to float, skipping")
            continue
        
        # Skip zero or negative values
        if billing_value_float <= 0:
            continue
        
        # Get other values
        milestone = row.get(col_milestone, '') if col_milestone else ''
        expected_date = row.get(col_expected_date, '') if col_expected_date else ''
        timeline = row.get(col_timeline, '') if col_timeline else ''
        
        # Clean values
        milestone_str = str(milestone).strip() if pd.notna(milestone) else ''
        timeline_str = str(timeline).strip() if pd.notna(timeline) else ''
        
        # Normalize the date with smart year inference
        expected_date_str = normalize_billing_date(expected_date, reference_months)
        
        # Create tranche object
        tranche = {
            "milestone": milestone_str,
            "billing_value": round_monetary(billing_value_float),
            "expected_billing_date_str": expected_date_str,
            "contractual_timeline_str": timeline_str
        }
        
        output_data["tranches"].append(tranche)
        logging.debug(f"Added tranche: {milestone_str} - {billing_value_float}")
    
    # Calculate total billing value
    output_data["total_billing_value"] = round_monetary(
        sum(t["billing_value"] for t in output_data["tranches"])
    )
    
    logging.info(f"Processed {len(output_data['tranches'])} tranches")
    logging.info(f"Total billing value: ₹{output_data['total_billing_value']:,.2f}")
    
    return output_data


def save_billing_data(data, run_dir):
    """Save billing data to JSON file."""
    if not run_dir:
        raise ValueError("run_dir is required - no legacy Data/ folder support")
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    output_file = run_dir / "funding_tranches_processed.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    logging.info(f"Saved to: {output_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process Billing Tracker Excel file')
    parser.add_argument('excel_file', help='Path to Billing Tracker Excel file')
    parser.add_argument('run_dir', help='Path to run output directory')
    parser.add_argument('--sheet', default='Sheet1', help='Sheet name (default: Sheet1)')
    parser.add_argument('--header-row', type=int, default=None, 
                        help='Header row index (default: auto-detect)')
    
    args = parser.parse_args()
    
    excel_file = Path(args.excel_file)
    run_dir = Path(args.run_dir)
    
    if not excel_file.exists():
        logging.error(f"Billing file not found: {excel_file}")
        sys.exit(1)
    
    # Process the file
    data = process_billing_file(excel_file, args.sheet, args.header_row)
    
    # Save to run directory only
    save_billing_data(data, run_dir)
    logging.info(f"Billing processing complete. Output: {run_dir / 'funding_tranches_processed.json'}")
