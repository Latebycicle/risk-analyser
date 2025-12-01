"""
Risk Analyser Configuration Settings

Centralized configuration for all constants, file paths, and keywords.
Import this module instead of hardcoding values in each script.

Usage:
    from config.settings import (
        DATA_DIR, RUNS_DIR, EXCEL_FILES,
        BUDGET_HEAD_KEYWORDS, MONTH_PATTERNS
    )
"""

from pathlib import Path
import logging

# ============================================================================
# DIRECTORY PATHS
# ============================================================================

# Get project root (parent of config/)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Main directories - ONLY Runs folder is used for outputs
RUNS_DIR = PROJECT_ROOT / "Runs"
CONFIG_DIR = PROJECT_ROOT / "config"

# Ensure directories exist
RUNS_DIR.mkdir(exist_ok=True)

# ============================================================================
# OUTPUT FILE NAMES (used within run directories)
# ============================================================================

# These are just filenames - actual paths are in run_dir
UC_JSON_FILENAME = "uc_processed.json"
ACTIVITY_JSON_FILENAME = "milestone_activities_processed.json"
FUNDING_JSON_FILENAME = "funding_tranches_processed.json"
RISK_REPORT_FILENAME = "master_risk_report.json"
FILE_INVENTORY_FILENAME = "file_inventory.json"
REPORT_FILENAME = "Project_Risk_Report.md"

# Sheet name defaults
UC_SHEET_NAME = "Sheet1"
ACTIVITY_SHEET_NAME = None  # Auto-detect
BILLING_SHEET_NAME = "Sheet1"


# ============================================================================
# COLUMN SEARCH KEYWORDS
# ============================================================================

# Budget head column keywords (case-insensitive search)
BUDGET_HEAD_KEYWORDS = ['budget head', 'budget_head', 'budget', 'head']

# Vendor/Role column keywords
VENDOR_ROLE_KEYWORDS = ['vendor', 'role', 'vendor/role', 'category', 'vendor role']

# Cost head column keywords
COST_HEAD_KEYWORDS = ['cost head', 'cost_head', 'cost', 'item', 'line item']

# Month column type keywords
PLAN_KEYWORDS = ['plan', 'planned', 'budget']
CLAIMS_KEYWORDS = ['claim', 'actual', 'invoice']
D365_KEYWORDS = ['d365', 'system', 'erp']

# Billing tracker column names
BILLING_COL_MILESTONE = "Payment Milestone/Document requirement Description"
BILLING_COL_EXPECTED_DATE = "Expected Date/Month of Billing"
BILLING_COL_BILLING_VALUE = "Billing Value"
BILLING_COL_TIMELINE = "Type of payment"


# ============================================================================
# DATE NORMALIZATION SETTINGS
# ============================================================================

# Standard date format for output (YYYY-MM)
STANDARD_DATE_FORMAT = "%Y-%m"

# Month abbreviation mapping for normalization
MONTH_ABBREVIATIONS = {
    'jan': '01', 'january': '01',
    'feb': '02', 'february': '02',
    'mar': '03', 'march': '03',
    'apr': '04', 'april': '04',
    'may': '05',
    'jun': '06', 'june': '06',
    'jul': '07', 'july': '07',
    'aug': '08', 'august': '08',
    'sep': '09', 'sept': '09', 'september': '09',
    'oct': '10', 'october': '10',
    'nov': '11', 'november': '11',
    'dec': '12', 'december': '12',
}

# Month patterns for regex matching
MONTH_PATTERNS = [
    r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
    r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december)'
]

# Number of rows to search for headers
HEADER_SEARCH_ROWS = [0, 1, 2, 3, 4, 5]


# ============================================================================
# PROCESSING SETTINGS
# ============================================================================

# Sparse storage: Skip months with all zero values
SPARSE_STORAGE_ENABLED = True

# Decimal places for monetary values
MONETARY_DECIMAL_PLACES = 2

# Maximum characters for metadata extraction
MAX_METADATA_CHARS = 5000

# Batch size for AI activity mapping
AI_BATCH_SIZE = 5


# ============================================================================
# OLLAMA / AI SETTINGS
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:12b"
OLLAMA_TIMEOUT = 300  # seconds
OLLAMA_CONTEXT_SIZE = 4096


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_FORMAT = '%(asctime)s - %(levelname)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.INFO


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


def get_runs_dir():
    """Return the runs directory path."""
    return RUNS_DIR


def normalize_month(date_string):
    """
    Normalize a date string to YYYY-MM format.
    
    Handles various input formats:
    - "Apr-25", "Apr 25" → "2025-04"
    - "April-2025", "April 2025" → "2025-04"
    - "4/25" → "2025-04"
    - "2025-04-01" → "2025-04"
    
    Args:
        date_string: Input date string
        
    Returns:
        Normalized date string in YYYY-MM format, or None if parsing fails
    """
    import re
    
    if not date_string or str(date_string).strip() == '':
        return None
    
    date_str = str(date_string).strip().lower()
    
    # Try to extract month and year
    month = None
    year = None
    
    # Pattern 0: ISO format FIRST (2025-04, 2025-04-01) - check before others
    iso_pattern = r'^(\d{4})[\s\-/]+(\d{1,2})'
    match = re.search(iso_pattern, date_str)
    if match:
        year = match.group(1)
        month = match.group(2).zfill(2)
        return f"{year}-{month}"
    
    # Pattern 1: Month name with year (Apr-25, April 2025, etc.)
    month_year_pattern = r'([a-z]+)[\s\-/]*(\d{2,4})'
    match = re.search(month_year_pattern, date_str)
    if match:
        month_text = match.group(1)
        year_text = match.group(2)
        
        # Look up month number
        for abbrev, month_num in MONTH_ABBREVIATIONS.items():
            if month_text.startswith(abbrev) or abbrev.startswith(month_text):
                month = month_num
                break
        
        # Normalize year to 4 digits
        if len(year_text) == 2:
            # Assume 20xx for years 00-99
            year = f"20{year_text}"
        else:
            year = year_text
    
    # Pattern 2: Numeric format (4/25, 04/2025)
    if month is None:
        numeric_pattern = r'(\d{1,2})[\s\-/]+(\d{2,4})'
        match = re.search(numeric_pattern, date_str)
        if match:
            month = match.group(1).zfill(2)
            year_text = match.group(2)
            if len(year_text) == 2:
                year = f"20{year_text}"
            else:
                year = year_text
    
    if month and year:
        return f"{year}-{month}"
    
    return None


def round_monetary(value):
    """
    Round a monetary value to the configured decimal places.
    
    Args:
        value: Numeric value to round
        
    Returns:
        Rounded float value
    """
    try:
        return round(float(value), MONETARY_DECIMAL_PLACES)
    except (ValueError, TypeError):
        return 0.0


# ============================================================================
# VALIDATION
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SETTINGS VALIDATION")
    print("=" * 60)
    
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Runs Directory: {RUNS_DIR}")
    
    print("\nOllama/AI Settings:")
    print(f"  URL: {OLLAMA_URL}")
    print(f"  Model: {OLLAMA_MODEL}")
    print(f"  Timeout: {OLLAMA_TIMEOUT}s")
    
    print("\nDate Normalization Test:")
    test_dates = [
        "Apr-25", "April-25", "April 2025", "4/25",
        "apr 25", "APR-25", "2025-04", "Mar"
    ]
    for date in test_dates:
        normalized = normalize_month(date)
        print(f"  '{date}' → '{normalized}'")
    
    print("\n" + "=" * 60)
    print("Settings loaded successfully!")
    print("=" * 60)
