"""
UC (Utilization Certificate) Processor - Live Variance Analysis

This script processes UC Excel files with Plan vs Actuals tracking.
It extracts budget lines, cost heads, and tracks planned vs actual spending 
to calculate real-time variances.

FEATURES:
- Robust date normalization (Apr-25, April 2025, 4/25 → 2025-04)
- Sparse storage (only stores months with non-zero values)
- Monetary values rounded to 2 decimal places
- Automatic column detection via keyword matching
- Variance tracking at line and global level

FIXES ADDRESSED:
- JSON bloat from duplicate months (Apr-25 vs April-25)
- Zero-value months taking up space
- Inconsistent decimal precision

USAGE:
    # As standalone:
    python process_uc.py
    
    # As module:
    from src.process_uc import process_uc_file
    result = process_uc_file("path/to/uc.xlsx")
"""

import pandas as pd
import json
import logging
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config.settings import (
        RUNS_DIR,
        BUDGET_HEAD_KEYWORDS, VENDOR_ROLE_KEYWORDS, COST_HEAD_KEYWORDS,
        PLAN_KEYWORDS, CLAIMS_KEYWORDS, D365_KEYWORDS,
        MONTH_ABBREVIATIONS, HEADER_SEARCH_ROWS,
        SPARSE_STORAGE_ENABLED, MONETARY_DECIMAL_PLACES,
        normalize_month, round_monetary,
    )
except ImportError:
    # Fallback for standalone execution
    RUNS_DIR = Path("Runs")
    BUDGET_HEAD_KEYWORDS = ['budget head', 'budget_head', 'budget', 'head']
    VENDOR_ROLE_KEYWORDS = ['vendor', 'role', 'vendor/role', 'category', 'vendor role']
    COST_HEAD_KEYWORDS = ['cost head', 'cost_head', 'cost', 'item', 'line item']
    PLAN_KEYWORDS = ['plan', 'planned', 'budget']
    CLAIMS_KEYWORDS = ['claim', 'actual', 'invoice']
    D365_KEYWORDS = ['d365', 'system', 'erp']
    HEADER_SEARCH_ROWS = [0, 1, 2, 3, 4, 5]
    SPARSE_STORAGE_ENABLED = True
    MONETARY_DECIMAL_PLACES = 2
    
    MONTH_ABBREVIATIONS = {
        'jan': '01', 'january': '01', 'feb': '02', 'february': '02',
        'mar': '03', 'march': '03', 'apr': '04', 'april': '04',
        'may': '05', 'jun': '06', 'june': '06', 'jul': '07', 'july': '07',
        'aug': '08', 'august': '08', 'sep': '09', 'sept': '09', 'september': '09',
        'oct': '10', 'october': '10', 'nov': '11', 'november': '11',
        'dec': '12', 'december': '12',
    }
    
    def normalize_month(date_string):
        """Normalize date string to YYYY-MM format."""
        if not date_string or str(date_string).strip() == '':
            return None
        date_str = str(date_string).strip().lower()
        month, year = None, None
        
        # Month name with year
        match = re.search(r'([a-z]+)[\s\-/]*(\d{2,4})', date_str)
        if match:
            month_text, year_text = match.group(1), match.group(2)
            for abbrev, month_num in MONTH_ABBREVIATIONS.items():
                if month_text.startswith(abbrev) or abbrev.startswith(month_text):
                    month = month_num
                    break
            year = f"20{year_text}" if len(year_text) == 2 else year_text
        
        if month and year:
            return f"{year}-{month}"
        return None
    
    def round_monetary(value):
        try:
            return round(float(value), MONETARY_DECIMAL_PLACES)
        except (ValueError, TypeError):
            return 0.0

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def clean_dataframe(df):
    """
    Clean the dataframe by removing completely empty rows and columns.
    
    Args:
        df: Raw DataFrame from Excel
        
    Returns:
        Cleaned DataFrame with empty rows/columns removed
    """
    original_shape = df.shape
    
    # Remove completely empty columns
    df = df.loc[:, df.apply(lambda col: col.notna().any() and col.astype(str).str.strip().str.len().sum() > 0)]
    
    # Remove completely empty rows
    df = df[df.apply(lambda row: row.notna().any() and row.astype(str).str.strip().str.len().sum() > 0, axis=1)]
    
    # Reset indices
    df = df.reset_index(drop=True)
    df.columns = range(len(df.columns))
    
    removed_rows = original_shape[0] - df.shape[0]
    removed_cols = original_shape[1] - df.shape[1]
    
    if removed_rows > 0 or removed_cols > 0:
        logging.info(f"Cleaned data: Removed {removed_rows} empty rows and {removed_cols} empty columns")
    
    return df


def find_column_by_header(df, header_keywords, search_rows=HEADER_SEARCH_ROWS):
    """
    Find column index by searching for keywords in header rows.
    
    Args:
        df: DataFrame to search
        header_keywords: List of possible header names (case-insensitive)
        search_rows: Row indices to search
    
    Returns:
        Column index if found, None otherwise
    """
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
        for col_idx in range(df.shape[1]):
            cell_value = df.iloc[row_idx, col_idx]
            if pd.isna(cell_value):
                continue
            cell_value = str(cell_value).strip().lower()
            if not cell_value:
                continue
            for keyword in header_keywords:
                if keyword.lower() in cell_value:
                    return col_idx
    return None


def find_month_column_map(df, search_rows=HEADER_SEARCH_ROWS):
    """
    Find all month columns and map them to plan/claims/d365 column indices.
    Uses normalized date keys to merge duplicate months.
    
    Returns:
        dict: {'2025-04': {'plan': 10, 'claims': 11, 'd365': 12}, ...}
    """
    month_map = {}
    
    # Month patterns for detection
    month_patterns = [
        r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december)'
    ]
    
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
            
        for col_idx in range(df.shape[1]):
            cell_value = df.iloc[row_idx, col_idx]
            if pd.isna(cell_value):
                continue
            cell_value = str(cell_value).strip()
            if not cell_value:
                continue
            
            # Check for month pattern
            month_match = None
            for pattern in month_patterns:
                match = re.search(pattern, cell_value)
                if match:
                    month_match = match.group(1)
                    break
            
            if not month_match:
                continue
            
            # For D365 columns, extract just the date part after "D365 "
            # e.g., "D365 Apr-25" → we normalize "Apr-25" not the whole string
            date_part = cell_value
            if 'd365' in cell_value.lower():
                # Extract month-year after D365
                d365_match = re.search(r'd365\s+(.+)', cell_value, re.IGNORECASE)
                if d365_match:
                    date_part = d365_match.group(1).strip()
            
            # Normalize the date to YYYY-MM format
            normalized_key = normalize_month(date_part)
            
            if normalized_key is None:
                # Fallback: just use the raw month name (shouldn't happen often)
                logging.warning(f"Could not normalize date: '{cell_value}'")
                continue
            
            # Initialize month entry if not exists
            if normalized_key not in month_map:
                month_map[normalized_key] = {'raw_headers': []}
            
            # Track the raw header for debugging
            month_map[normalized_key]['raw_headers'].append(cell_value)
            
            # Determine column type based on keywords
            cell_lower = cell_value.lower()
            
            if any(keyword in cell_lower for keyword in PLAN_KEYWORDS):
                month_map[normalized_key]['plan'] = col_idx
                logging.debug(f"Found PLAN column for {normalized_key} at col {col_idx}: '{cell_value}'")
            elif any(keyword in cell_lower for keyword in CLAIMS_KEYWORDS):
                month_map[normalized_key]['claims'] = col_idx
                logging.debug(f"Found CLAIMS column for {normalized_key} at col {col_idx}: '{cell_value}'")
            elif any(keyword in cell_lower for keyword in D365_KEYWORDS):
                month_map[normalized_key]['d365'] = col_idx
                logging.debug(f"Found D365 column for {normalized_key} at col {col_idx}: '{cell_value}'")
        
        # If we found month columns in this row, don't search other rows
        if month_map:
            break
    
    # Log merged months (debugging duplicate detection)
    for key, data in month_map.items():
        if len(data.get('raw_headers', [])) > 1:
            logging.info(f"Merged duplicate month headers: {data['raw_headers']} → {key}")
    
    return month_map


def find_total_column(df, search_rows=HEADER_SEARCH_ROWS):
    """Find the total/plan total column."""
    keywords = ['plan total', 'total plan', 'total', 'grand total']
    
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
        for col_idx in range(df.shape[1]):
            cell_value = str(df.iloc[row_idx, col_idx]).strip().lower()
            for keyword in keywords:
                if keyword in cell_value and 'plan' in cell_value:
                    return col_idx
    return None


def clean_value(value):
    """Helper function to clean and round monetary values."""
    if pd.isna(value):
        return 0.0
    value_str = str(value).replace(',', '')
    try:
        return round_monetary(float(value_str))
    except ValueError:
        return 0.0


def is_non_zero_month(month_data):
    """Check if a month has any non-zero values worth storing."""
    if not SPARSE_STORAGE_ENABLED:
        return True
    
    planned = month_data.get('planned', 0)
    total_spent = month_data.get('total_spent', 0)
    
    # Store if either planned or spent is non-zero
    return planned != 0 or total_spent != 0


def process_uc_file(excel_file, sheet_name='Sheet1', run_dir=None):
    """
    Process a UC Excel file and extract budget/variance data.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Sheet name to process
        run_dir: Optional directory to save output
        
    Returns:
        Dictionary containing processed UC data
    """
    logging.info(f"Processing UC file: {excel_file}")
    
    # Load Excel file
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    logging.info(f"Loaded Excel with shape (raw): {df.shape}")
    
    # Clean the dataframe
    df = clean_dataframe(df)
    logging.info(f"Loaded Excel with shape (cleaned): {df.shape}")
    
    # Find key columns
    logging.info("Searching for required columns...")
    
    budget_head_col = find_column_by_header(df, BUDGET_HEAD_KEYWORDS)
    vendor_role_col = find_column_by_header(df, VENDOR_ROLE_KEYWORDS)
    cost_head_col = find_column_by_header(df, COST_HEAD_KEYWORDS)
    
    # Find month column mapping with normalized keys
    month_map = find_month_column_map(df)
    
    # Sort months chronologically
    month_names = sorted(month_map.keys())
    
    # Find total column
    plan_total_column = find_total_column(df)
    
    # Validate required columns
    if budget_head_col is None:
        raise ValueError("Could not find 'Budget Head' column in UC file")
    if cost_head_col is None:
        raise ValueError("Could not find 'Cost Head' column in UC file")
    if not month_map:
        raise ValueError("Could not find any month columns in UC file")
    
    logging.info(f"Column Mapping:")
    logging.info(f"  Budget Head: Column {budget_head_col}")
    logging.info(f"  Vendor/Role: Column {vendor_role_col if vendor_role_col else 'Not found (optional)'}")
    logging.info(f"  Cost Head: Column {cost_head_col}")
    logging.info(f"  Months: {len(month_names)} found (normalized)")
    logging.info(f"  Month keys: {month_names}")
    
    # Initialize output structure
    output_data = {
        "monthly_data": {},
        "cumulative_data": {},
        "budget_lines": {},
        "processing_metadata": {
            "sparse_storage": SPARSE_STORAGE_ENABLED,
            "decimal_places": MONETARY_DECIMAL_PLACES,
            "date_format": "YYYY-MM (normalized)",
            "months_processed": len(month_names),
        }
    }
    
    # Determine data start row
    data_start_row = None
    for i in range(3):
        if pd.notna(df.iloc[i, budget_head_col]):
            cell_text = str(df.iloc[i, budget_head_col]).lower()
            if 'budget' in cell_text or 'head' in cell_text or cell_text in ['s.no', 'sr.no', '#']:
                continue
            else:
                data_start_row = i
                break
    
    if data_start_row is None:
        data_start_row = 3
    
    logging.info(f"Data appears to start at row {data_start_row}")
    
    # Process each data row
    logging.info("Extracting budget lines with variance tracking...")
    
    for i in range(data_start_row, df.shape[0]):
        budget_head = df.iloc[i, budget_head_col]
        
        # Skip empty or total rows
        if pd.isna(budget_head) or str(budget_head).strip() == '':
            continue
        
        budget_head_str = str(budget_head).lower()
        if 'total' in budget_head_str or 'subtotal' in budget_head_str or 'grand' in budget_head_str:
            continue
        
        # Get vendor/role and cost head
        vendor_role = df.iloc[i, vendor_role_col] if vendor_role_col is not None else None
        cost_head = df.iloc[i, cost_head_col]
        
        # Create budget line key
        if pd.notna(budget_head) and vendor_role_col is not None and pd.notna(vendor_role):
            budget_line_key = f"{str(budget_head).strip()} - {str(vendor_role).strip()}"
        elif pd.notna(budget_head):
            budget_line_key = str(budget_head).strip()
        else:
            continue
        
        cost_head_value = str(cost_head).strip() if pd.notna(cost_head) else None
        
        # Initialize budget line if not exists
        if budget_line_key not in output_data["budget_lines"]:
            output_data["budget_lines"][budget_line_key] = {
                "budget_head": str(budget_head).strip(),
                "cost_heads": [],
                "vendor_role_category": str(vendor_role).strip() if pd.notna(vendor_role) else None,
                "total_planned": 0.0,
                "total_spent": 0.0,
                "total_variance": 0.0,
                "monthly_data": {}
            }
        
        # Process each month
        line_total_planned = 0.0
        line_total_spent = 0.0
        
        for month_key in month_names:
            month_cols = month_map[month_key]
            
            plan_col = month_cols.get('plan')
            claims_col = month_cols.get('claims')
            d365_col = month_cols.get('d365')
            
            planned_val = clean_value(df.iloc[i, plan_col]) if plan_col is not None else 0.0
            claims_val = clean_value(df.iloc[i, claims_col]) if claims_col is not None else 0.0
            d365_val = clean_value(df.iloc[i, d365_col]) if d365_col is not None else 0.0
            
            total_spent = round_monetary(claims_val + d365_val)
            variance = round_monetary(planned_val - total_spent)
            
            # Build month data
            month_data = {
                "planned": planned_val,
                "claims": claims_val,
                "d365": d365_val,
                "total_spent": total_spent,
                "variance": variance
            }
            
            # Only store if non-zero (sparse storage)
            if is_non_zero_month(month_data):
                if month_key not in output_data["budget_lines"][budget_line_key]["monthly_data"]:
                    output_data["budget_lines"][budget_line_key]["monthly_data"][month_key] = {
                        "planned": 0.0,
                        "claims": 0.0,
                        "d365": 0.0,
                        "total_spent": 0.0,
                        "variance": 0.0
                    }
                
                # Aggregate values
                line_month = output_data["budget_lines"][budget_line_key]["monthly_data"][month_key]
                line_month["planned"] = round_monetary(line_month["planned"] + planned_val)
                line_month["claims"] = round_monetary(line_month["claims"] + claims_val)
                line_month["d365"] = round_monetary(line_month["d365"] + d365_val)
                line_month["total_spent"] = round_monetary(line_month["total_spent"] + total_spent)
                line_month["variance"] = round_monetary(line_month["variance"] + variance)
            
            line_total_planned += planned_val
            line_total_spent += total_spent
        
        # Update budget line totals
        output_data["budget_lines"][budget_line_key]["total_planned"] = round_monetary(
            output_data["budget_lines"][budget_line_key]["total_planned"] + line_total_planned
        )
        output_data["budget_lines"][budget_line_key]["total_spent"] = round_monetary(
            output_data["budget_lines"][budget_line_key]["total_spent"] + line_total_spent
        )
        output_data["budget_lines"][budget_line_key]["total_variance"] = round_monetary(
            output_data["budget_lines"][budget_line_key]["total_planned"] - 
            output_data["budget_lines"][budget_line_key]["total_spent"]
        )
        
        # Add cost head
        if cost_head_value and cost_head_value not in output_data["budget_lines"][budget_line_key]["cost_heads"]:
            output_data["budget_lines"][budget_line_key]["cost_heads"].append(cost_head_value)
    
    logging.info(f"Extracted {len(output_data['budget_lines'])} budget line items")
    
    # Calculate Global Monthly Aggregates (only non-zero months)
    logging.info("Calculating global monthly aggregates...")
    
    for month_key in month_names:
        month_total_planned = 0.0
        month_total_claims = 0.0
        month_total_d365 = 0.0
        month_total_spent = 0.0
        month_total_variance = 0.0
        
        for budget_line in output_data["budget_lines"].values():
            if month_key in budget_line["monthly_data"]:
                month_data = budget_line["monthly_data"][month_key]
                month_total_planned += month_data["planned"]
                month_total_claims += month_data["claims"]
                month_total_d365 += month_data["d365"]
                month_total_spent += month_data["total_spent"]
                month_total_variance += month_data["variance"]
        
        global_month_data = {
            "planned": round_monetary(month_total_planned),
            "claims": round_monetary(month_total_claims),
            "d365": round_monetary(month_total_d365),
            "total_spent": round_monetary(month_total_spent),
            "variance": round_monetary(month_total_variance)
        }
        
        # Only store non-zero months globally too
        if is_non_zero_month(global_month_data):
            output_data["monthly_data"][month_key] = global_month_data
    
    # Calculate Global Cumulative Data (only for non-zero months)
    logging.info("Calculating global cumulative data...")
    
    cumulative_planned = 0.0
    cumulative_spent = 0.0
    
    for month_key in month_names:
        if month_key in output_data["monthly_data"]:
            month_data = output_data["monthly_data"][month_key]
            cumulative_planned += month_data["planned"]
            cumulative_spent += month_data["total_spent"]
            
            output_data["cumulative_data"][month_key] = {
                "cumulative_planned": round_monetary(cumulative_planned),
                "cumulative_spent": round_monetary(cumulative_spent),
                "cumulative_variance": round_monetary(cumulative_planned - cumulative_spent)
            }
    
    # Grand Totals
    grand_total_planned = round_monetary(
        sum(line["total_planned"] for line in output_data["budget_lines"].values())
    )
    grand_total_spent = round_monetary(
        sum(line["total_spent"] for line in output_data["budget_lines"].values())
    )
    
    output_data["grand_totals"] = {
        "total_planned": grand_total_planned,
        "total_spent": grand_total_spent,
        "total_variance": round_monetary(grand_total_planned - grand_total_spent)
    }
    
    # Log size savings
    stored_months = len(output_data["monthly_data"])
    total_months = len(month_names)
    savings_pct = ((total_months - stored_months) / total_months * 100) if total_months > 0 else 0
    
    logging.info(f"\n{'='*60}")
    logging.info(f"PROCESSING COMPLETE")
    logging.info(f"{'='*60}")
    logging.info(f"Budget Lines: {len(output_data['budget_lines'])}")
    logging.info(f"Months in source: {total_months}")
    logging.info(f"Months stored (non-zero): {stored_months}")
    logging.info(f"Storage savings: {savings_pct:.1f}%")
    logging.info(f"\nGrand Totals:")
    logging.info(f"  Total Planned: ₹{grand_total_planned:,.2f}")
    logging.info(f"  Total Spent: ₹{grand_total_spent:,.2f}")
    logging.info(f"  Total Variance: ₹{output_data['grand_totals']['total_variance']:,.2f}")
    logging.info(f"{'='*60}\n")
    
    return output_data


def save_uc_data(output_data, run_dir):
    """
    Save UC processed data to JSON file.
    
    Args:
        output_data: Processed UC data dictionary
        run_dir: Directory for run output (REQUIRED)
    """
    if not run_dir:
        raise ValueError("run_dir is required - no legacy Data/ folder support")
    
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    output_file = run_dir / "uc_processed.json"
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    logging.info(f"Saved to: {output_file}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process UC Excel file')
    parser.add_argument('excel_file', help='Path to UC Excel file')
    parser.add_argument('run_dir', help='Path to run output directory')
    parser.add_argument('--sheet', default='Sheet1', help='Sheet name (default: Sheet1)')
    
    args = parser.parse_args()
    
    excel_file = Path(args.excel_file)
    run_dir = Path(args.run_dir)
    
    if not excel_file.exists():
        logging.error(f"UC Excel file not found: {excel_file}")
        sys.exit(1)
    
    # Process the file
    output_data = process_uc_file(excel_file, args.sheet)
    
    # Save to run directory only
    save_uc_data(output_data, run_dir)
    logging.info(f"UC processing complete. Output: {run_dir / 'uc_processed.json'}")
