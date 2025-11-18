import pandas as pd
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define the file
EXCEL_FILE = 'Data/Ivanti UC.xlsx'
SHEET_NAME = 'Sheet1'

# Load the Excel file into a pandas DataFrame
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, header=None)

logging.info(f"Loaded Excel with shape: {df.shape}")

# Create the final output dictionary
output_data = {}
output_data["monthly_planned_spending"] = {}
output_data["cumulative_planned_spending"] = {}
output_data["budget_line_totals"] = {}


def clean_value(value):
    """Helper function to clean monetary values"""
    if pd.isna(value):
        return 0.0
    value_str = str(value).replace(',', '')
    try:
        return float(value_str)
    except ValueError:
        return 0.0


# Define the month Plan column indices based on the actual structure
# Plan columns: Apr-25 (14), May-25 (17), Jun-25 (20), Jul-25 (23), Aug-25 (26), Sep-25 (29),
#               Oct-25 (32), Nov-25 (35), Dec-25 (38), Jan-26 (41), Feb-26 (44), Mar-26 (47)
month_columns = [14, 17, 20, 23, 26, 29, 32, 35, 38, 41, 44, 47]

# Column 50 contains "Plan Total 2025-26" - the total for each budget line
plan_total_column = 50

# Get month names from row 1 (header row)
month_names = [str(df.iloc[1, col]).replace('Plan ', '').strip() for col in month_columns]
logging.info(f"Months: {month_names}")

# Extract Budget Line Totals from the "Plan Total 2025-26" column
# Column 8 = Budget head, Column 9 = Vendor/Role Category
logging.info("Extracting budget line totals...")

# Iterate through all data rows (starting from row 2)
for i in range(2, df.shape[0]):
    # Get budget head from column 8
    budget_head = df.iloc[i, 8]
    vendor_role = df.iloc[i, 9]
    
    # Skip if both are empty (end of data)
    if pd.isna(budget_head) and pd.isna(vendor_role):
        continue
    
    # Create a combined line item name
    if pd.notna(budget_head) and pd.notna(vendor_role):
        line_item_name = f"{str(budget_head).strip()} - {str(vendor_role).strip()}"
    elif pd.notna(budget_head):
        line_item_name = str(budget_head).strip()
    else:
        continue
    
    # Get the total from the "Plan Total 2025-26" column
    line_item_total = clean_value(df.iloc[i, plan_total_column])
    
    # Add to or update the budget line total
    if line_item_name in output_data["budget_line_totals"]:
        output_data["budget_line_totals"][line_item_name] += line_item_total
    else:
        output_data["budget_line_totals"][line_item_name] = line_item_total

logging.info(f"Extracted {len(output_data['budget_line_totals'])} budget line items")

# Extract Total Monthly Planned Spending
# Sum all plan values for each month across all rows
logging.info("Calculating total monthly planned spending...")
for idx, month_col in enumerate(month_columns):
    month_name = month_names[idx]
    # Sum all values in this column for all data rows
    monthly_total = 0.0
    for i in range(2, df.shape[0]):
        value = df.iloc[i, month_col]
        monthly_total += clean_value(value)
    
    output_data["monthly_planned_spending"][month_name] = monthly_total
    logging.debug(f"  {month_name}: {monthly_total}")

# Calculate Cumulative Monthly Spending
logging.info("Calculating cumulative planned spending...")
cumulative_total = 0.0

for month_name in month_names:
    monthly_value = output_data["monthly_planned_spending"][month_name]
    cumulative_total += monthly_value
    output_data["cumulative_planned_spending"][month_name] = cumulative_total
    logging.debug(f"  {month_name}: {cumulative_total}")

# Write to JSON file (will replace existing file)
output_file = "Data/uc_processed.json"
with open(output_file, "w") as json_file:
    json.dump(output_data, json_file, indent=4)

logging.info(f"\nProcessing complete! Output saved to '{output_file}'")
logging.info(f"Total budget line items: {len(output_data['budget_line_totals'])}")
logging.info(f"Total months tracked: {len(output_data['monthly_planned_spending'])}")
logging.info(f"Final cumulative total: {cumulative_total}")
