"""
UC (Utilization Certificate) Processor - Live Variance Analysis

This script processes UC Excel files with Plan vs Actuals tracking.
It extracts budget lines, cost heads, and tracks planned vs actual spending (Claims + D365)
to calculate real-time variances.

FEATURES:
- Automatically finds columns by searching for header keywords
- Tracks PLAN, CLAIMS, and D365 columns for each month
- Calculates variance (Plan - Actuals) at line and global level
- Tracks cumulative spending over time
- Adapts to different UC formats without code changes
- Outputs to unique run directories for version tracking

USAGE:
1. Place your UC Excel file in the Data/ folder
2. Update EXCEL_FILE and SHEET_NAME in the configuration section below
3. If your UC uses different column names, add them to the keyword lists
4. Run: python process_uc.py

OUTPUT:
- Runs/run_YYYYMMDD_HHMMSS/uc_processed.json with structured budget, actuals, and variance data
"""

import pandas as pd
import json
import logging
import re
from run_manager import get_current_run_id, get_run_output_dir, create_new_run

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Excel file settings
EXCEL_FILE = 'Data/Tata Bluescope UC Plan.xlsx'
SHEET_NAME = 'Sheet1'

# Column search keywords (add alternatives if your UC uses different names)
BUDGET_HEAD_KEYWORDS = ['budget head', 'budget_head', 'budget', 'head']
VENDOR_ROLE_KEYWORDS = ['vendor', 'role', 'vendor/role', 'category', 'vendor role']
COST_HEAD_KEYWORDS = ['cost head', 'cost_head', 'cost', 'item', 'line item']

# Month column type keywords
PLAN_KEYWORDS = ['plan', 'planned', 'budget']
CLAIMS_KEYWORDS = ['claim', 'actual', 'invoice']
D365_KEYWORDS = ['d365', 'system', 'erp']

# Number of rows to search for headers (expanded to handle files with more whitespace)
HEADER_SEARCH_ROWS = [0, 1, 2, 3, 4, 5]

# ============================================================================

# Load the Excel file into a pandas DataFrame
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, header=None)

logging.info(f"Loaded Excel with shape (raw): {df.shape}")


def clean_dataframe(df):
    """
    Clean the dataframe by removing completely empty rows and columns,
    and trimming leading/trailing empty rows and columns.
    
    Args:
        df: Raw DataFrame from Excel
        
    Returns:
        Cleaned DataFrame with empty rows/columns removed
    """
    original_shape = df.shape
    
    # Step 1: Remove completely empty columns (all NaN or whitespace)
    df = df.loc[:, df.apply(lambda col: col.notna().any() and col.astype(str).str.strip().str.len().sum() > 0)]
    
    # Step 2: Remove completely empty rows (all NaN or whitespace)
    df = df[df.apply(lambda row: row.notna().any() and row.astype(str).str.strip().str.len().sum() > 0, axis=1)]
    
    # Step 3: Reset index after removing rows
    df = df.reset_index(drop=True)
    
    # Step 4: Reset columns to be sequential integers
    df.columns = range(len(df.columns))
    
    cleaned_shape = df.shape
    removed_rows = original_shape[0] - cleaned_shape[0]
    removed_cols = original_shape[1] - cleaned_shape[1]
    
    if removed_rows > 0 or removed_cols > 0:
        logging.info(f"Cleaned data: Removed {removed_rows} empty rows and {removed_cols} empty columns")
    
    return df


# Clean the dataframe
df = clean_dataframe(df)
logging.info(f"Loaded Excel with shape (cleaned): {df.shape}")


def find_column_by_header(df, header_keywords, search_rows=[0, 1, 2]):
    """
    Find column index by searching for keywords in header rows.
    
    Args:
        df: DataFrame to search
        header_keywords: List of possible header names/keywords (case-insensitive)
        search_rows: List of row indices to search (default: first 3 rows)
    
    Returns:
        Column index if found, None otherwise
    """
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
        for col_idx in range(df.shape[1]):
            cell_value = df.iloc[row_idx, col_idx]
            # Skip NaN and empty values
            if pd.isna(cell_value):
                continue
            cell_value = str(cell_value).strip().lower()
            if not cell_value:  # Skip if empty after stripping
                continue
            for keyword in header_keywords:
                if keyword.lower() in cell_value:
                    logging.debug(f"Found '{keyword}' at row {row_idx}, col {col_idx}: '{cell_value}'")
                    return col_idx
    return None



def find_month_column_map(df, search_rows=[0, 1, 2]):
    """
    Find all month columns and map them to plan/claims/d365 column indices.
    Returns dict: {'Apr-25': {'plan': 10, 'claims': 11, 'd365': 12}, ...}
    """
    month_map = {}
    
    # Common month abbreviations and patterns
    month_patterns = [
        r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december)'
    ]
    
    # Search through header rows
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
            
        for col_idx in range(df.shape[1]):
            cell_value = df.iloc[row_idx, col_idx]
            # Skip NaN and empty values
            if pd.isna(cell_value):
                continue
            cell_value = str(cell_value).strip()
            if not cell_value:  # Skip if empty after stripping
                continue
            
            # Check if this cell contains a month pattern
            month_match = None
            for pattern in month_patterns:
                match = re.search(pattern, cell_value)
                if match:
                    month_match = match.group(1)
                    break
            
            if not month_match:
                continue
            
            # Extract clean month name (e.g., "Apr-25" from "Plan Apr-25")
            # Look for patterns like "Apr-25", "Apr 25", "April-2025"
            clean_name = None
            
            # Try to find month-year pattern (e.g., Apr-25, Apr 25)
            month_year_pattern = r'([A-Za-z]{3,9})[\s-](\d{2,4})'
            match = re.search(month_year_pattern, cell_value)
            if match:
                month_part = match.group(1)
                year_part = match.group(2)
                # Standardize to "Mon-YY" format
                if len(year_part) == 4:
                    year_part = year_part[-2:]
                clean_name = f"{month_part.capitalize()}-{year_part}"
            else:
                # Fallback: just use the month name with a default year
                clean_name = month_match.capitalize()
            
            # Initialize month entry if not exists
            if clean_name not in month_map:
                month_map[clean_name] = {}
            
            # Determine column type based on keywords
            cell_lower = cell_value.lower()
            
            # Check for plan keywords
            if any(keyword in cell_lower for keyword in PLAN_KEYWORDS):
                month_map[clean_name]['plan'] = col_idx
                logging.debug(f"Found PLAN column for {clean_name} at col {col_idx}: '{cell_value}'")
            
            # Check for claims keywords
            elif any(keyword in cell_lower for keyword in CLAIMS_KEYWORDS):
                month_map[clean_name]['claims'] = col_idx
                logging.debug(f"Found CLAIMS column for {clean_name} at col {col_idx}: '{cell_value}'")
            
            # Check for D365 keywords
            elif any(keyword in cell_lower for keyword in D365_KEYWORDS):
                month_map[clean_name]['d365'] = col_idx
                logging.debug(f"Found D365 column for {clean_name} at col {col_idx}: '{cell_value}'")
        
        # If we found month columns in this row, don't search other rows
        if month_map:
            break
    
    return month_map


def find_total_column(df, search_rows=[0, 1, 2]):
    """
    Find the total/plan total column.
    """
    keywords = ['plan total', 'total plan', 'total', 'grand total']
    
    for row_idx in search_rows:
        if row_idx >= df.shape[0]:
            continue
        for col_idx in range(df.shape[1]):
            cell_value = str(df.iloc[row_idx, col_idx]).strip().lower()
            for keyword in keywords:
                if keyword in cell_value and 'plan' in cell_value:
                    logging.debug(f"Found total column at col {col_idx}: '{cell_value}'")
                    return col_idx
    
    return None


logging.info("Searching for required columns...")

# Find key columns by their headers
budget_head_col = find_column_by_header(df, BUDGET_HEAD_KEYWORDS, HEADER_SEARCH_ROWS)
vendor_role_col = find_column_by_header(df, VENDOR_ROLE_KEYWORDS, HEADER_SEARCH_ROWS)
cost_head_col = find_column_by_header(df, COST_HEAD_KEYWORDS, HEADER_SEARCH_ROWS)

# Find month column mapping (plan/claims/d365)
month_map = find_month_column_map(df, HEADER_SEARCH_ROWS)
month_names = sorted(month_map.keys())  # Sort chronologically if possible

# Find total column
plan_total_column = find_total_column(df, HEADER_SEARCH_ROWS)

# Validate required columns were found
if budget_head_col is None:
    raise ValueError("Could not find 'Budget Head' column in UC file")
if cost_head_col is None:
    raise ValueError("Could not find 'Cost Head' column in UC file")
if not month_map:
    raise ValueError("Could not find any month columns in UC file")
if plan_total_column is None:
    logging.warning("Could not find 'Plan Total' column - will calculate from monthly values")

logging.info(f"Column Mapping:")
logging.info(f"  Budget Head: Column {budget_head_col}")
logging.info(f"  Vendor/Role: Column {vendor_role_col if vendor_role_col else 'Not found (optional)'}")
logging.info(f"  Cost Head: Column {cost_head_col}")
logging.info(f"  Plan Total: Column {plan_total_column if plan_total_column else 'Not found (will calculate)'}")
logging.info(f"  Month Columns: {len(month_names)} months found")
logging.info(f"  Months: {month_names}")

# Log month mapping details
for month in month_names:
    cols = month_map[month]
    plan_col = cols.get('plan', 'N/A')
    claims_col = cols.get('claims', 'N/A')
    d365_col = cols.get('d365', 'N/A')
    logging.info(f"    {month}: Plan={plan_col}, Claims={claims_col}, D365={d365_col}")

# Create the final output dictionary with variance tracking
output_data = {}
output_data["monthly_data"] = {}  # Global monthly aggregates
output_data["cumulative_data"] = {}  # Global cumulative tracking
output_data["budget_lines"] = {}  # Budget lines with variance tracking


def clean_value(value):
    """Helper function to clean monetary values"""
    if pd.isna(value):
        return 0.0
    value_str = str(value).replace(',', '')
    try:
        return float(value_str)
    except ValueError:
        return 0.0


# Determine where data rows start (after headers)
# Find first row where budget_head_col has non-empty data
data_start_row = None
for i in range(3):  # Check first 3 rows
    if pd.notna(df.iloc[i, budget_head_col]):
        # Check if this looks like a header (contains text like "budget", "head", etc.)
        cell_text = str(df.iloc[i, budget_head_col]).lower()
        if 'budget' in cell_text or 'head' in cell_text or cell_text in ['s.no', 'sr.no', '#']:
            continue
        else:
            data_start_row = i
            break

# If not found in first 3 rows, assume data starts at row 3
if data_start_row is None:
    data_start_row = 3
    logging.info(f"Data appears to start at row {data_start_row} (default)")
else:
    logging.info(f"Data appears to start at row {data_start_row}")

# Extract Budget Lines with Variance Analysis
logging.info("Extracting budget lines with variance tracking...")

# Iterate through all data rows
for i in range(data_start_row, df.shape[0]):
    # Get budget head
    budget_head = df.iloc[i, budget_head_col]
    
    # Skip if budget head is empty (end of data)
    if pd.isna(budget_head) or str(budget_head).strip() == '':
        continue
    
    # Skip if this looks like a subtotal or total row
    budget_head_str = str(budget_head).lower()
    if 'total' in budget_head_str or 'subtotal' in budget_head_str or 'grand' in budget_head_str:
        continue
    
    # Get vendor/role and cost head
    vendor_role = df.iloc[i, vendor_role_col] if vendor_role_col is not None else None
    cost_head = df.iloc[i, cost_head_col]
    
    # Create a combined budget line key
    if pd.notna(budget_head) and vendor_role_col is not None and pd.notna(vendor_role):
        budget_line_key = f"{str(budget_head).strip()} - {str(vendor_role).strip()}"
    elif pd.notna(budget_head):
        budget_line_key = str(budget_head).strip()
    else:
        continue
    
    # Get cost head
    cost_head_value = str(cost_head).strip() if pd.notna(cost_head) else None
    
    # Initialize budget line if it doesn't exist
    if budget_line_key not in output_data["budget_lines"]:
        output_data["budget_lines"][budget_line_key] = {
            "budget_head": str(budget_head).strip(),
            "vendor_role_category": str(vendor_role).strip() if pd.notna(vendor_role) else None,
            "total_planned": 0.0,
            "total_spent": 0.0,
            "total_variance": 0.0,
            "monthly_data": {},
            "cost_heads": []
        }
    
    # Process each month's data (plan, claims, d365, variance)
    line_total_planned = 0.0
    line_total_spent = 0.0
    
    for month_name in month_names:
        month_cols = month_map[month_name]
        
        # Get values from each column type (default to 0 if not found)
        plan_col = month_cols.get('plan')
        claims_col = month_cols.get('claims')
        d365_col = month_cols.get('d365')
        
        planned_val = clean_value(df.iloc[i, plan_col]) if plan_col is not None else 0.0
        claims_val = clean_value(df.iloc[i, claims_col]) if claims_col is not None else 0.0
        d365_val = clean_value(df.iloc[i, d365_col]) if d365_col is not None else 0.0
        
        # Calculate spent and variance
        total_spent = claims_val + d365_val
        variance = planned_val - total_spent
        
        # Initialize month data for this budget line if not exists
        if month_name not in output_data["budget_lines"][budget_line_key]["monthly_data"]:
            output_data["budget_lines"][budget_line_key]["monthly_data"][month_name] = {
                "planned": 0.0,
                "claims": 0.0,
                "d365": 0.0,
                "total_spent": 0.0,
                "variance": 0.0
            }
        
        # Aggregate values for this budget line
        output_data["budget_lines"][budget_line_key]["monthly_data"][month_name]["planned"] += planned_val
        output_data["budget_lines"][budget_line_key]["monthly_data"][month_name]["claims"] += claims_val
        output_data["budget_lines"][budget_line_key]["monthly_data"][month_name]["d365"] += d365_val
        output_data["budget_lines"][budget_line_key]["monthly_data"][month_name]["total_spent"] += total_spent
        output_data["budget_lines"][budget_line_key]["monthly_data"][month_name]["variance"] += variance
        
        # Accumulate line totals
        line_total_planned += planned_val
        line_total_spent += total_spent
    
    # Update budget line totals
    output_data["budget_lines"][budget_line_key]["total_planned"] += line_total_planned
    output_data["budget_lines"][budget_line_key]["total_spent"] += line_total_spent
    output_data["budget_lines"][budget_line_key]["total_variance"] = (
        output_data["budget_lines"][budget_line_key]["total_planned"] - 
        output_data["budget_lines"][budget_line_key]["total_spent"]
    )
    
    # Add cost head to the list if it exists and isn't already tracked
    if cost_head_value and cost_head_value not in output_data["budget_lines"][budget_line_key]["cost_heads"]:
        output_data["budget_lines"][budget_line_key]["cost_heads"].append(cost_head_value)

logging.info(f"Extracted {len(output_data['budget_lines'])} budget line items")

# Calculate Global Monthly Aggregates
logging.info("Calculating global monthly aggregates...")
for month_name in month_names:
    month_total_planned = 0.0
    month_total_claims = 0.0
    month_total_d365 = 0.0
    month_total_spent = 0.0
    month_total_variance = 0.0
    
    # Sum across all budget lines
    for budget_line in output_data["budget_lines"].values():
        if month_name in budget_line["monthly_data"]:
            month_data = budget_line["monthly_data"][month_name]
            month_total_planned += month_data["planned"]
            month_total_claims += month_data["claims"]
            month_total_d365 += month_data["d365"]
            month_total_spent += month_data["total_spent"]
            month_total_variance += month_data["variance"]
    
    output_data["monthly_data"][month_name] = {
        "planned": month_total_planned,
        "claims": month_total_claims,
        "d365": month_total_d365,
        "total_spent": month_total_spent,
        "variance": month_total_variance
    }
    logging.debug(f"  {month_name}: Planned={month_total_planned}, Spent={month_total_spent}, Variance={month_total_variance}")

# Calculate Global Cumulative Data
logging.info("Calculating global cumulative data...")
cumulative_planned = 0.0
cumulative_spent = 0.0

for month_name in month_names:
    month_data = output_data["monthly_data"][month_name]
    cumulative_planned += month_data["planned"]
    cumulative_spent += month_data["total_spent"]
    cumulative_variance = cumulative_planned - cumulative_spent
    
    output_data["cumulative_data"][month_name] = {
        "cumulative_planned": cumulative_planned,
        "cumulative_spent": cumulative_spent,
        "cumulative_variance": cumulative_variance
    }
    logging.debug(f"  {month_name}: Cumulative Planned={cumulative_planned}, Spent={cumulative_spent}, Variance={cumulative_variance}")

# Calculate Grand Totals
grand_total_planned = sum(line["total_planned"] for line in output_data["budget_lines"].values())
grand_total_spent = sum(line["total_spent"] for line in output_data["budget_lines"].values())
grand_total_variance = grand_total_planned - grand_total_spent

output_data["grand_totals"] = {
    "total_planned": grand_total_planned,
    "total_spent": grand_total_spent,
    "total_variance": grand_total_variance
}

# Get or create run directory
run_id = get_current_run_id()
if run_id is None:
    run_id, run_dir = create_new_run()
else:
    run_dir = get_run_output_dir()

# Write to JSON file in run directory
output_file = run_dir / "uc_processed.json"
with open(output_file, "w") as json_file:
    json.dump(output_data, json_file, indent=4)

# Also save a copy to Data/ for backward compatibility
legacy_output = "Data/uc_processed.json"
with open(legacy_output, "w") as json_file:
    json.dump(output_data, json_file, indent=4)

logging.info(f"\n{'='*60}")
logging.info(f"LIVE VARIANCE ANALYSIS - Processing Complete!")
logging.info(f"{'='*60}")
logging.info(f"Run ID: {run_id}")
logging.info(f"Output saved to: '{output_file}'")
logging.info(f"Legacy copy: '{legacy_output}'")
logging.info(f"\nSummary:")
logging.info(f"  Budget Lines: {len(output_data['budget_lines'])}")
logging.info(f"  Months Tracked: {len(output_data['monthly_data'])}")
logging.info(f"  Total Cost Heads: {sum(len(item['cost_heads']) for item in output_data['budget_lines'].values())}")
logging.info(f"\nGrand Totals:")
logging.info(f"  Total Planned: ₹{grand_total_planned:,.2f}")
logging.info(f"  Total Spent: ₹{grand_total_spent:,.2f}")
logging.info(f"  Total Variance: ₹{grand_total_variance:,.2f}")

# Calculate variance percentage
if grand_total_planned > 0:
    variance_pct = (grand_total_variance / grand_total_planned) * 100
    logging.info(f"  Variance %: {variance_pct:.1f}%")

# Show budget utilization
if grand_total_planned > 0:
    utilization_pct = (grand_total_spent / grand_total_planned) * 100
    logging.info(f"  Budget Utilization: {utilization_pct:.1f}%")

logging.info(f"{'='*60}\n")
