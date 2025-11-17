import pandas as pd
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Define file and sheet names
EXCEL_FILE = 'Data/Ivanti activity sheet_v2.xlsx'
SHEET_NAME = 'Activity sheet '  # Note the trailing space!

# Load the specific sheet from the Excel file
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

# Focus on these columns
df = df[["Milestone", "Activity ", "Start date ", "End date "]]

logging.info(f"Loaded {len(df)} rows from Excel")
logging.info(f"Sample start dates: {df['Start date '].head(10).tolist()}")
logging.info(f"Start date data types: {df['Start date '].dtype}")


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
        activity = row["Activity "]
        start_date = row["Start date "]
        end_date = row["End date "]
        
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

# Write to JSON file (will replace existing file)
output_file = "Data/milestone_activities_processed.json"
with open(output_file, "w") as json_file:
    json.dump(ordered_data, json_file, indent=4)

logging.info(f"\nProcessing complete! Output saved to '{output_file}'")
logging.info(f"Total milestones: {len(ordered_data)}")
logging.info(f"Total activities: {sum(len(activities) for activities in ordered_data.values())}")
logging.info("Milestones ordered by earliest start date")
