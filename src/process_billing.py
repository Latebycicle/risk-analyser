"""
Billing Tracker Processor

Extracts funding tranches and billing milestones from Excel files.
Outputs structured JSON for cash flow analysis.

Usage:
    python -m src.process_billing
"""

import pandas as pd
import json
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import (
        DATA_DIR,
        BILLING_COL_MILESTONE, BILLING_COL_EXPECTED_DATE,
        BILLING_COL_BILLING_VALUE, BILLING_COL_TIMELINE,
        round_monetary,
    )
    from src.run_manager import get_current_run_id, get_run_output_dir, create_new_run
except ImportError:
    DATA_DIR = PROJECT_ROOT / "Data"
    BILLING_COL_MILESTONE = "Payment Milestone/Document requirement Description"
    BILLING_COL_EXPECTED_DATE = "Expected Date/Month of Billing"
    BILLING_COL_BILLING_VALUE = "Billing Value"
    BILLING_COL_TIMELINE = "Type of payment"
    
    def round_monetary(value):
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return 0.0
    
    from run_manager import get_current_run_id, get_run_output_dir, create_new_run

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def process_billing_file(excel_file, sheet_name='Sheet1', header_row=2):
    """
    Process a billing tracker Excel file.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Sheet name to process
        header_row: Row index where headers are located (0-indexed)
        
    Returns:
        Dictionary containing billing data
    """
    excel_file = Path(excel_file)
    logging.info(f"Processing billing file: {excel_file}")
    
    # Load the sheet with headers at specified row
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
    
    logging.info(f"Loaded {len(df)} rows from Excel")
    logging.info(f"Columns found: {df.columns.tolist()}")
    
    # Initialize output structure
    output_data = {
        "total_billing_value": 0.0,
        "tranches": [],
        "processing_metadata": {
            "source_file": excel_file.name,
            "sheet_name": sheet_name,
        }
    }
    
    # Process each row
    for idx, row in df.iterrows():
        # Get billing value
        billing_value = row.get(BILLING_COL_BILLING_VALUE)
        
        # Stop if billing value is empty (end of data)
        if pd.isna(billing_value):
            logging.info(f"Reached end of data at row {idx}")
            break
        
        # Get other values
        milestone = row.get(BILLING_COL_MILESTONE, '')
        expected_date = row.get(BILLING_COL_EXPECTED_DATE, '')
        timeline = row.get(BILLING_COL_TIMELINE, '')
        
        # Clean values
        milestone_str = str(milestone).strip() if pd.notna(milestone) else ''
        expected_date_str = str(expected_date).strip() if pd.notna(expected_date) else ''
        timeline_str = str(timeline).strip() if pd.notna(timeline) else ''
        
        # Create tranche object
        tranche = {
            "milestone": milestone_str,
            "billing_value": round_monetary(billing_value),
            "expected_billing_date_str": expected_date_str,
            "contractual_timeline_str": timeline_str
        }
        
        output_data["tranches"].append(tranche)
        logging.debug(f"Added tranche: {milestone_str} - {billing_value}")
    
    # Calculate total billing value
    output_data["total_billing_value"] = round_monetary(
        sum(t["billing_value"] for t in output_data["tranches"])
    )
    
    logging.info(f"Processed {len(output_data['tranches'])} tranches")
    logging.info(f"Total billing value: ₹{output_data['total_billing_value']:,.2f}")
    
    return output_data


def save_billing_data(data, run_dir=None, legacy_path=None):
    """Save billing data to JSON files."""
    
    if run_dir:
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        output_file = run_dir / "funding_tranches_processed.json"
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
    EXCEL_FILE = DATA_DIR / 'Ivanti billing & collections tracker.xlsx'
    
    if not EXCEL_FILE.exists():
        EXCEL_FILE = Path('Data/Ivanti billing & collections tracker.xlsx')
    
    if not EXCEL_FILE.exists():
        logging.error(f"Billing file not found: {EXCEL_FILE}")
        sys.exit(1)
    
    # Process the file
    data = process_billing_file(EXCEL_FILE)
    
    # Get run directory
    try:
        run_id = get_current_run_id()
        if run_id is None:
            run_id, run_dir = create_new_run()
        else:
            run_dir = get_run_output_dir()
        
        save_billing_data(data, run_dir, DATA_DIR / "funding_tranches_processed.json")
        logging.info(f"Run ID: {run_id}")
    except Exception as e:
        save_billing_data(data, legacy_path=DATA_DIR / "funding_tranches_processed.json")
