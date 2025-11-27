import pandas as pd
import json
from datetime import datetime
import logging
from run_manager import get_current_run_id, get_run_output_dir, create_new_run

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define file and sheet names
EXCEL_FILE = 'Data/Tata Bluescope_Plan_v1.0_20-Nov-2025.xlsx'
SHEET_NAME = None  # Will auto-detect

# Auto-detect sheet name if not specified
if SHEET_NAME is None:
    excel_file = pd.ExcelFile(EXCEL_FILE)
    sheet_names = excel_file.sheet_names
    logging.info(f"Available sheets: {sheet_names}")
    
    # Try to find sheet with "activity" or "plan" in the name
    for sheet in sheet_names:
        sheet_lower = sheet.lower().strip()
        if 'activity' in sheet_lower or 'plan' in sheet_lower:
            SHEET_NAME = sheet
            logging.info(f"Auto-detected sheet: '{SHEET_NAME}'")
            break
    
    # If not found, use first sheet
    if SHEET_NAME is None:
        SHEET_NAME = sheet_names[0]
        logging.info(f"Using first sheet: '{SHEET_NAME}'")

# Load the specific sheet from the Excel file
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, header=None)

# Try to find header row (look for row containing "milestone" and "activity")
header_row = None
for i in range(min(5, len(df))):
    row_str = ' '.join(df.iloc[i].astype(str).str.lower())
    if ('milestone' in row_str or 'cost head' in row_str) and 'activity' in row_str:
        header_row = i
        logging.info(f"Found header row at index {i}")
        break

if header_row is not None:
    # Use the found row as headers
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
else:
    logging.warning("Could not find header row, using first row as headers")
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

# Clean column names (remove trailing/leading whitespace and handle NaN)
df.columns = [str(col).strip() if pd.notna(col) else f"Unnamed_{i}" for i, col in enumerate(df.columns)]

logging.info(f"Columns found: {df.columns.tolist()}")

# Try to identify required columns flexibly
milestone_col = None
activity_col = None
start_date_col = None
end_date_col = None

for col in df.columns:
    col_lower = col.lower()
    if ('milestone' in col_lower or 'cost head' in col_lower) and milestone_col is None:
        milestone_col = col
    elif 'activity' in col_lower and 'date' not in col_lower and activity_col is None:
        activity_col = col
    elif 'start' in col_lower and ('date' in col_lower or 'month' in col_lower) and start_date_col is None:
        start_date_col = col
    elif 'end' in col_lower and ('date' in col_lower or 'month' in col_lower) and end_date_col is None:
        end_date_col = col

# If we still can't find columns, try by position (common patterns)
if milestone_col is None:
    milestone_col = df.columns[0]  # First column often milestone
    logging.warning(f"Using first column as Milestone: '{milestone_col}'")
    
if activity_col is None and len(df.columns) > 1:
    # Look for a column with more text content
    for col in df.columns[1:]:
        if df[col].astype(str).str.len().mean() > 10:  # Activity descriptions are usually longer
            activity_col = col
            logging.warning(f"Using column with long text as Activity: '{activity_col}'")
            break

logging.info(f"Detected columns: Milestone='{milestone_col}', Activity='{activity_col}', Start='{start_date_col}', End='{end_date_col}'")

# Check if we have required columns
if milestone_col is None or activity_col is None:
    raise ValueError("Could not find required columns (Milestone/Activity). Please check the file format.")

# Focus on available columns
if start_date_col and end_date_col:
    df = df[[milestone_col, activity_col, start_date_col, end_date_col]]
    df.columns = ["Milestone", "Activity", "Start date", "End date"]
elif start_date_col:
    df = df[[milestone_col, activity_col, start_date_col]]
    df.columns = ["Milestone", "Activity", "Start date"]
    df["End date"] = None
elif end_date_col:
    df = df[[milestone_col, activity_col, end_date_col]]
    df.columns = ["Milestone", "Activity", "End date"]
    df["Start date"] = None
else:
    df = df[[milestone_col, activity_col]]
    df.columns = ["Milestone", "Activity"]
    df["Start date"] = None
    df["End date"] = None
    logging.warning("No date columns found - activities will not have dates")

logging.info(f"Loaded {len(df)} rows from Excel")
logging.info(f"Sample start dates: {df['Start date'].head(10).tolist()}")
logging.info(f"Start date data types: {df['Start date'].dtype}")


def parse_date(date_string):
    """
    Helper function to parse date strings.
    
    Args:
        date_string: A date string in format '12-Sep-25' or pandas Timestamp
        
    Returns:
        datetime object if successful, None otherwise
    """
    if pd.isna(date_string):
        return None
    
    # If it's already a datetime/Timestamp object from pandas, convert to datetime
    if isinstance(date_string, (datetime, pd.Timestamp)):
        return date_string.to_pydatetime() if hasattr(date_string, 'to_pydatetime') else date_string
    
    # Convert to string and try parsing
    date_str = str(date_string).strip()
    
    try:
        return datetime.strptime(date_str, '%d-%b-%y')
    except (ValueError, TypeError) as e:
        logging.warning(f"Failed to parse date '{date_str}': {e}")
        return None


# Group by Milestone
grouped = df.groupby("Milestone")

# Create final dictionary to hold all data
final_data = {}

# Iterate through each milestone group
for milestone, group in grouped:
    activities_list = []
    
    # Iterate through each row in the group
    for idx, row in group.iterrows():
        activity = row["Activity"]
        start_date = row["Start date"]
        end_date = row["End date"]
        
        # Parse dates using helper function
        start_date_obj = parse_date(start_date)
        end_date_obj = parse_date(end_date)
        
        # Calculate duration
        if start_date_obj is not None and end_date_obj is not None:
            timedelta = end_date_obj - start_date_obj
            duration_in_days = timedelta.days + 1  # Inclusive
        else:
            duration_in_days = None
        
        # Create activity object
        activity_object = {
            "activity": activity,
            "start_date_iso": start_date_obj.strftime('%Y-%m-%d') if start_date_obj is not None else None,
            "end_date_iso": end_date_obj.strftime('%Y-%m-%d') if end_date_obj is not None else None,
            "duration_in_days": duration_in_days
        }
        
        # Append to activities list
        activities_list.append(activity_object)
    
    # Add to final dictionary
    final_data[milestone] = activities_list

# Sort milestones by earliest start date
# Create a list of (milestone, activities, earliest_date) tuples
milestone_with_dates = []
for milestone, activities in final_data.items():
    # Find the earliest start date among all activities in this milestone
    start_dates = [
        datetime.fromisoformat(act['start_date_iso']) 
        for act in activities 
        if act['start_date_iso'] is not None
    ]
    earliest_date = min(start_dates) if start_dates else datetime.max
    milestone_with_dates.append((milestone, activities, earliest_date))

# Sort by earliest date
milestone_with_dates.sort(key=lambda x: x[2])

# Create ordered dictionary
ordered_data = {milestone: activities for milestone, activities, _ in milestone_with_dates}

# Get or create run directory
run_id = get_current_run_id()
if run_id is None:
    run_id, run_dir = create_new_run()
else:
    run_dir = get_run_output_dir()

# Write to JSON file in run directory
output_file = run_dir / "milestone_activities_processed.json"
with open(output_file, "w") as json_file:
    json.dump(ordered_data, json_file, indent=4)

# Also save a copy to Data/ for backward compatibility
legacy_output = "Data/milestone_activities_processed.json"
with open(legacy_output, "w") as json_file:
    json.dump(ordered_data, json_file, indent=4)

logging.info(f"\nProcessing complete!")
logging.info(f"Run ID: {run_id}")
logging.info(f"Output saved to: '{output_file}'")
logging.info(f"Legacy copy: '{legacy_output}'")
logging.info(f"Total milestones: {len(ordered_data)}")
logging.info(f"Total activities: {sum(len(activities) for activities in ordered_data.values())}")
logging.info("Milestones ordered by earliest start date")
