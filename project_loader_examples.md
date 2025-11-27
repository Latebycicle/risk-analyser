# Project Loader - Usage Guide

## Overview

The `ProjectLoader` class robustly identifies project files and extracts context from any folder structure. It uses heuristic keyword matching with automatic conflict resolution.

## Basic Usage

```python
from project_loader import ProjectLoader

# Initialize with project folder
loader = ProjectLoader("Data")

# Step 1: Identify key files automatically
files = loader.identify_files()

# Step 2: Extract context from additional files
context_text, source_files = loader.load_context_text()

# Step 3: Check readiness
summary = loader.get_summary()

if summary['ready_for_analysis']:
    print("✓ All required files found!")
    print(f"UC: {summary['uc_path']}")
    print(f"Activity: {summary['activity_path']}")
    print(f"Billing: {summary['billing_path']}")
else:
    print("✗ Missing required files")
```

## File Identification Rules

### Keyword Matching (Case-Insensitive)

| File Type | Keywords | Example Files |
|-----------|----------|---------------|
| **UC** | `uc`, `utilization`, `budget` | `Ivanti UC.xlsx`, `Budget_2025.xlsx` |
| **Activity** | `activity`, `plan`, `timeline` | `Activity_Plan.xlsx`, `Project_Timeline.xlsx` |
| **Billing** | `billing`, `tracker`, `tranche` | `Billing_Tracker.xlsx`, `Tranche_Report.xlsx` |
| **Context** | Any other supported file | `Proposal.pdf`, `Team_Structure.xlsx` |

### Supported File Types

- **Project Files:** `.xlsx`, `.xls`, `.xlsm`
- **Context Files:** `.pdf`, `.xlsx`, `.xls`, `.xlsm`, `.docx`, `.txt`

### Conflict Resolution

If a file matches multiple categories (e.g., "Budget_Activity_Plan.xlsx"), it's assigned based on **priority**:

**Priority Order (highest to lowest):**
1. **UC** (Priority 3) - Most specific
2. **Billing** (Priority 2)
3. **Activity** (Priority 1)

Example:
- `"UC_Activity_Plan.xlsx"` → Assigned to **UC** ✓
- `"Billing_Activity_Tracker.xlsx"` → Assigned to **Billing** ✓
- File with warning: `⚠ File matches multiple categories ['uc', 'activity']. Assigned to 'uc' (highest priority).`

## Context Extraction

The `load_context_text()` method extracts text from all context files:

```python
context_text, source_files = loader.load_context_text()

print(f"Extracted {len(context_text):,} characters")
print(f"From files: {source_files}")
```

### Extraction Methods by File Type

| Format | Method | Library | Notes |
|--------|--------|---------|-------|
| PDF | Page-by-page text extraction | `pypdf` | Install: `pip install pypdf` |
| Excel | All sheets to markdown tables | `pandas` | Built-in |
| DOCX | Paragraph extraction | `python-docx` | Install: `pip install python-docx` |
| TXT | Direct read | Built-in | UTF-8 encoding |

### Output Format

```
============================================================
SOURCE: filename.pdf (PDF)
============================================================
--- Page 1 ---
[content]
--- Page 2 ---
[content]

============================================================
SOURCE: data.xlsx (Excel)
============================================================
--- Sheet: Summary ---
Shape: 10 rows × 5 columns
[markdown table]
```

## Advanced Usage

### Integrating with Risk Analysis

```python
from project_loader import ProjectLoader

# Step 1: Load project
loader = ProjectLoader("Data")
files = loader.identify_files()

# Step 2: Verify all required files found
summary = loader.get_summary()
if not summary['ready_for_analysis']:
    raise ValueError("Missing required project files")

# Step 3: Use identified paths in processors
import process_uc
import process_activities
import process_billing

uc_data = process_uc.process_file(files['uc'])
activity_data = process_activities.process_file(files['activity'])
billing_data = process_billing.process_file(files['billing'])

# Step 4: Extract additional context for AI
extra_context, sources = loader.load_context_text()

# Step 5: Combine with metadata for richer AI analysis
combined_context = metadata + "\n\n" + extra_context
strategic_risks = check_strategic_risks(combined_context, budget_dict)
```

### Using Absolute Paths

All file paths returned are absolute, making them safe to use from any working directory:

```python
files = loader.identify_files()

# Safe to use from anywhere
uc_path = files['uc']  
# Returns: /full/path/to/project/Data/Ivanti UC.xlsx

# Can pass directly to pandas or other libraries
import pandas as pd
df = pd.read_excel(uc_path)
```

## Installation Requirements

### Core (Required)
```bash
pip install pandas
```

### Optional (for full functionality)
```bash
# For PDF extraction
pip install pypdf

# For Word document extraction
pip install python-docx
```

## Command Line Usage

Run directly to test a folder:

```bash
# Test with default "Data" folder
python project_loader.py

# Test with custom folder
python project_loader.py /path/to/project/folder
```

## Error Handling

```python
from project_loader import ProjectLoader

try:
    loader = ProjectLoader("NonExistentFolder")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Folder not found: NonExistentFolder

# Check for missing files
loader = ProjectLoader("Data")
loader.identify_files()

summary = loader.get_summary()
if not summary['uc_found']:
    print("⚠ Warning: UC file not found!")
if not summary['ready_for_analysis']:
    print("✗ Cannot proceed: Missing required files")
```

## Output Structure

### files Dictionary
```python
{
    'uc': '/absolute/path/to/UC.xlsx',
    'activity': '/absolute/path/to/Activity.xlsx',
    'billing': '/absolute/path/to/Billing.xlsx',
    'context': [
        '/absolute/path/to/file1.pdf',
        '/absolute/path/to/file2.txt'
    ]
}
```

### summary Dictionary
```python
{
    'uc_found': True,
    'activity_found': True,
    'billing_found': True,
    'context_files_count': 2,
    'ready_for_analysis': True,
    'uc_path': '/absolute/path/to/UC.xlsx',
    'activity_path': '/absolute/path/to/Activity.xlsx',
    'billing_path': '/absolute/path/to/Billing.xlsx'
}
```

## Best Practices

1. **Naming Convention:** Use clear keywords in filenames for automatic detection
2. **Conflict Avoidance:** Avoid multiple keywords in same filename (e.g., "UC_Activity.xlsx")
3. **Context Files:** Place supplementary documents in project folder for automatic extraction
4. **Validation:** Always check `ready_for_analysis` before proceeding
5. **Logging:** Enable logging to see file identification process: `logging.basicConfig(level=logging.INFO)`
