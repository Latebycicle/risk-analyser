# Risk Analyser Refactoring Summary

## Overview

This document summarizes the refactoring of the Risk Analyser codebase to be modular, clean, and efficient.

## New Project Structure

```
risk-analyser/
├── src/                        # Python source modules
│   ├── __init__.py
│   ├── process_uc.py           # UC processor (with date normalization)
│   ├── process_billing.py      # Billing tracker processor
│   ├── process_activities.py   # Activity plan processor
│   ├── run_risk_analysis.py    # Main entry point
│   ├── generate_report.py      # Report generation
│   ├── compliance_checker.py   # AI-powered compliance checking
│   ├── metadata_extractor.py   # Smart metadata extraction
│   ├── project_loader.py       # Automatic file identification
│   └── run_manager.py          # Run directory management
│
├── config/                     # Configuration
│   ├── __init__.py
│   └── settings.py             # All constants and file paths
│
├── data/                       # Input files (Excel, PDF)
│   └── [project files]
│
├── runs/                       # Output (timestamped folders)
│   └── run_YYYY-MM-DD_HH-MM-SS/
│       ├── run_metadata.json
│       ├── uc_processed.json
│       ├── milestone_activities_processed.json
│       └── master_risk_report.json
│
├── refactor_project.py         # Script to set up folder structure
├── readme.md
├── RUN_MANAGEMENT.md
└── TODO.md
```

## Key Improvements

### 1. JSON Bloat Fix (69% Size Reduction)

**Problem**: The `uc_processed.json` file was bloated due to:
- Duplicate months: `Apr-25`, `April-25`, `April 2025` stored separately
- Zero-value months stored unnecessarily
- Inconsistent decimal precision

**Solution**:

#### Date Normalization
All date formats now normalize to `YYYY-MM`:
- `Apr-25` → `2025-04`
- `April 2025` → `2025-04`
- `4/25` → `2025-04`
- `D365 Apr-25` → `2025-04`

Implementation: `config/settings.py:normalize_month()`

#### Sparse Storage
Only months with non-zero `planned` or `total_spent` values are stored:
```python
# Before: 14 months stored (many with all zeros)
# After: 5 months stored (only non-zero)
# Savings: 64% reduction in month entries
```

#### Result
- **Before**: 59,779 bytes
- **After**: 18,254 bytes
- **Reduction**: 69%

### 2. Configuration Centralization

All hardcoded values moved to `config/settings.py`:

```python
# Directories
DATA_DIR, RUNS_DIR, REPORT_DIR

# Keywords for column detection
BUDGET_HEAD_KEYWORDS = ['budget head', 'budget_head', 'budget', 'head']
VENDOR_ROLE_KEYWORDS = ['vendor', 'role', 'vendor/role', 'category']
COST_HEAD_KEYWORDS = ['cost head', 'cost_head', 'cost', 'item', 'line item']
PLAN_KEYWORDS = ['plan', 'planned', 'budget']
CLAIMS_KEYWORDS = ['claim', 'actual', 'invoice']
D365_KEYWORDS = ['d365', 'system', 'erp']

# AI Settings
OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

# Processing settings
SPARSE_STORAGE_ENABLED = True
MONETARY_DECIMAL_PLACES = 2
```

### 3. Timestamped Run Directories

Every analysis run creates a new folder:
```
runs/run_2025-11-27_10-30-00/
├── run_metadata.json      # Run status, timestamps
├── uc_processed.json      # Processed UC data
├── milestone_activities_processed.json
└── master_risk_report.json
```

### 4. Dead Code Identification

The following files are NOT called by `run_risk_analysis.py`:
- `test_system.py` - Test file
- `list_runs.py` - Utility script
- `project_loader_examples.md` - Documentation

Recommendation: Move to `archive/` folder or delete.

## Usage

### Run the refactoring script
```bash
python refactor_project.py
```

### Run the main analysis
```bash
# From project root:
python -m src.run_risk_analysis

# Or:
cd src && python run_risk_analysis.py
```

### Run individual processors
```bash
python -m src.process_uc
python -m src.process_activities
python -m src.process_billing
```

### Validate configuration
```bash
python config/settings.py
```

## Files Created

| File | Description |
|------|-------------|
| `refactor_project.py` | Shell script to reorganize folder structure |
| `config/settings.py` | Centralized configuration with all constants |
| `config/__init__.py` | Package exports |
| `src/__init__.py` | Package definition |
| `src/process_uc.py` | Refactored UC processor with sparse storage |
| `src/process_billing.py` | Refactored billing processor |
| `src/process_activities.py` | Refactored activity processor |
| `src/run_risk_analysis.py` | Refactored main entry point |
| `src/run_manager.py` | Run directory management |
| `src/compliance_checker.py` | AI compliance checking |
| `src/metadata_extractor.py` | Smart metadata extraction |

## Testing

Run the configuration validation:
```
$ python config/settings.py

Date Normalization Test:
  'Apr-25' → '2025-04'
  'April-25' → '2025-04'
  'April 2025' → '2025-04'
  '4/25' → '2025-04'
  'apr 25' → '2025-04'
  'APR-25' → '2025-04'
  '2025-04' → '2025-04'
```

## Migration Notes

1. The old files in root directory (`process_uc.py`, etc.) can be deleted after verifying the `src/` versions work.
2. The `Data/` folder should be replaced with `data/` (lowercase).
3. The `Runs/` folder should be replaced with `runs/` (lowercase).
4. Update any external scripts to use `python -m src.run_risk_analysis`.
