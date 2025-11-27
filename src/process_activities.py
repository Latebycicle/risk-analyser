"""
Activity Plan Processor

Extracts milestone activities and timelines from Excel files.
Outputs structured JSON for risk analysis.

Usage:
    python -m src.process_activities
"""

import pandas as pd
import json
import sys
from datetime import datetime
import logging
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import DATA_DIR
    from src.run_manager import get_current_run_id, get_run_output_dir, create_new_run
except ImportError:
    DATA_DIR = PROJECT_ROOT / "Data"
    from run_manager import get_current_run_id, get_run_output_dir, create_new_run

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def parse_date(date_string):
    """
    Parse date strings to datetime objects.
    
    Args:
        date_string: A date string or pandas Timestamp
        
    Returns:
        datetime object if successful, None otherwise
    """
    if pd.isna(date_string):
        return None
    
    if isinstance(date_string, (datetime, pd.Timestamp)):
        return date_string.to_pydatetime() if hasattr(date_string, 'to_pydatetime') else date_string
    
    date_str = str(date_string).strip()
    
    # Try common formats
    formats = ['%d-%b-%y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    logging.warning(f"Failed to parse date: '{date_str}'")
    return None


def process_activities_file(excel_file, sheet_name=None):
    """
    Process an activity plan Excel file.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Sheet name (auto-detected if None)
        
    Returns:
        Dictionary of milestones with activities
    """
    excel_file = Path(excel_file)
    logging.info(f"Processing activities file: {excel_file}")
    
    # Auto-detect sheet name if not specified
    if sheet_name is None:
        xl_file = pd.ExcelFile(excel_file)
        sheet_names = xl_file.sheet_names
        logging.info(f"Available sheets: {sheet_names}")
        
        for sheet in sheet_names:
            sheet_lower = sheet.lower().strip()
            if 'activity' in sheet_lower or 'plan' in sheet_lower:
                sheet_name = sheet
                logging.info(f"Auto-detected sheet: '{sheet_name}'")
                break
        
        if sheet_name is None:
            sheet_name = sheet_names[0]
            logging.info(f"Using first sheet: '{sheet_name}'")
    
    # Load the sheet
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    
    # Find header row
    header_row = None
    for i in range(min(5, len(df))):
        row_str = ' '.join(df.iloc[i].astype(str).str.lower())
        if ('milestone' in row_str or 'cost head' in row_str) and 'activity' in row_str:
            header_row = i
            logging.info(f"Found header row at index {i}")
            break
    
    if header_row is not None:
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
    else:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
    
    # Clean column names
    df.columns = [str(col).strip() if pd.notna(col) else f"Unnamed_{i}" for i, col in enumerate(df.columns)]
    
    logging.info(f"Columns found: {df.columns.tolist()}")
    
    # Identify required columns
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
    
    # Fallback column detection
    if milestone_col is None:
        milestone_col = df.columns[0]
        logging.warning(f"Using first column as Milestone: '{milestone_col}'")
    
    if activity_col is None and len(df.columns) > 1:
        for col in df.columns[1:]:
            if df[col].astype(str).str.len().mean() > 10:
                activity_col = col
                logging.warning(f"Using column with long text as Activity: '{activity_col}'")
                break
    
    if milestone_col is None or activity_col is None:
        raise ValueError("Could not find required columns")
    
    # Select columns
    selected_cols = [milestone_col, activity_col]
    if start_date_col:
        selected_cols.append(start_date_col)
    if end_date_col:
        selected_cols.append(end_date_col)
    
    df = df[selected_cols]
    
    # Rename columns for consistency
    new_names = ["Milestone", "Activity"]
    if start_date_col:
        new_names.append("Start date")
    if end_date_col:
        new_names.append("End date")
    df.columns = new_names
    
    # Add missing columns
    if "Start date" not in df.columns:
        df["Start date"] = None
    if "End date" not in df.columns:
        df["End date"] = None
    
    logging.info(f"Loaded {len(df)} rows")
    
    # Group by Milestone
    grouped = df.groupby("Milestone")
    
    final_data = {}
    
    for milestone, group in grouped:
        activities_list = []
        
        for idx, row in group.iterrows():
            activity = row["Activity"]
            start_date = row["Start date"]
            end_date = row["End date"]
            
            start_date_obj = parse_date(start_date)
            end_date_obj = parse_date(end_date)
            
            if start_date_obj and end_date_obj:
                duration_in_days = (end_date_obj - start_date_obj).days + 1
            else:
                duration_in_days = None
            
            activity_object = {
                "activity": activity,
                "start_date_iso": start_date_obj.strftime('%Y-%m-%d') if start_date_obj else None,
                "end_date_iso": end_date_obj.strftime('%Y-%m-%d') if end_date_obj else None,
                "duration_in_days": duration_in_days
            }
            
            activities_list.append(activity_object)
        
        final_data[milestone] = activities_list
    
    # Sort milestones by earliest start date
    milestone_with_dates = []
    for milestone, activities in final_data.items():
        start_dates = [
            datetime.fromisoformat(act['start_date_iso']) 
            for act in activities 
            if act['start_date_iso']
        ]
        earliest_date = min(start_dates) if start_dates else datetime.max
        milestone_with_dates.append((milestone, activities, earliest_date))
    
    milestone_with_dates.sort(key=lambda x: x[2])
    
    ordered_data = {milestone: activities for milestone, activities, _ in milestone_with_dates}
    
    logging.info(f"Processed {len(ordered_data)} milestones, {sum(len(a) for a in ordered_data.values())} activities")
    
    return ordered_data


def save_activities_data(data, run_dir=None, legacy_path=None):
    """Save activities data to JSON files."""
    
    if run_dir:
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        output_file = run_dir / "milestone_activities_processed.json"
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Saved to: {output_file}")
    
    if legacy_path:
        legacy_path = Path(legacy_path)
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        with open(legacy_path, "w") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Legacy copy: {legacy_path}")


if __name__ == "__main__":
    # Default file path
    EXCEL_FILE = DATA_DIR / 'Tata Bluescope_Plan_v1.0_20-Nov-2025.xlsx'
    
    if not EXCEL_FILE.exists():
        EXCEL_FILE = Path('Data/Tata Bluescope_Plan_v1.0_20-Nov-2025.xlsx')
    
    if not EXCEL_FILE.exists():
        logging.error(f"Activity file not found: {EXCEL_FILE}")
        sys.exit(1)
    
    # Process the file
    data = process_activities_file(EXCEL_FILE)
    
    # Get run directory
    try:
        run_id = get_current_run_id()
        if run_id is None:
            run_id, run_dir = create_new_run()
        else:
            run_dir = get_run_output_dir()
        
        save_activities_data(data, run_dir, DATA_DIR / "milestone_activities_processed.json")
        logging.info(f"Run ID: {run_id}")
    except Exception as e:
        save_activities_data(data, legacy_path=DATA_DIR / "milestone_activities_processed.json")
