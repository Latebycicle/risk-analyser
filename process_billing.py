import pandas as pd
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define file and sheet names
EXCEL_FILE = 'Data/Ivanti billing & collections tracker.xlsx'
SHEET_NAME = 'Sheet1'

# Load the specific sheet from the Excel file
# IMPORTANT: The headers are on row 3 (0-indexed, so header=2)
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, header=2)

logging.info(f"Loaded {len(df)} rows from Excel")
logging.info(f"Columns found: {df.columns.tolist()}")

# Define the column names we need to read
COL_MILESTONE = "Payment Milestone/Document requirement Description"
COL_EXPECTED_DATE = "Expected Date/Month of Billing"
COL_BILLING_VALUE = "Billing Value"
COL_TIMELINE = "Type of payment"

# Calculate the total project value
total_billing_value = df[COL_BILLING_VALUE].sum()
logging.info(f"Total billing value: {total_billing_value}")

# Create a final output dictionary
output_data = {}
output_data["total_billing_value"] = total_billing_value
output_data["tranches"] = []

# Iterate through each row of the DataFrame
for idx, row in df.iterrows():
    # Get the values for the four key columns
    milestone = row[COL_MILESTONE]
    expected_date = row[COL_EXPECTED_DATE]
    billing_value = row[COL_BILLING_VALUE]
    timeline = row[COL_TIMELINE]
    
    # Check if billing_value is empty or NaN - if so, break the loop
    if pd.isna(billing_value):
        logging.info(f"Reached end of data at row {idx}")
        break
    
    # Clean the strings
    milestone_str = str(milestone).strip()
    expected_date_str = str(expected_date).strip()
    timeline_str = str(timeline).strip()
    
    # Create a tranche_object dictionary
    tranche_object = {
        "milestone": milestone_str,
        "billing_value": float(billing_value),
        "expected_billing_date_str": expected_date_str,
        "contractual_timeline_str": timeline_str
    }
    
    # Append to the tranches list
    output_data["tranches"].append(tranche_object)
    logging.debug(f"Added tranche: {milestone_str} - {billing_value}")

# Write to JSON file (will replace existing file)
output_file = "Data/funding_tranches_processed.json"
with open(output_file, "w") as json_file:
    json.dump(output_data, json_file, indent=4)

logging.info(f"\nProcessing complete! Output saved to '{output_file}'")
logging.info(f"Total tranches: {len(output_data['tranches'])}")
logging.info(f"Total billing value: {output_data['total_billing_value']}")
