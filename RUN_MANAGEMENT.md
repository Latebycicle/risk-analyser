# Run Management System

## Overview

The risk analysis system now uses a **run-based output system** where each analysis creates a unique run directory with a timestamp-based ID. All processor outputs (UC, Activity, Billing) are saved together in the same run folder, making it easy to track versions and compare different analyses.

## Directory Structure

```
Runs/
├── .current_run                    # Tracks the active run ID
├── run_20251125_151730/           # Example run directory
│   ├── run_metadata.json          # Run status and timestamps
│   ├── uc_processed.json          # UC processor output
│   ├── milestone_activities_processed.json  # Activity processor output
│   └── master_risk_report.json    # Risk analysis output (if generated)
├── run_20251125_160230/           # Another run
│   └── ...
└── ...
```

## Benefits

1. **Version Control**: Every run is preserved with a unique timestamp
2. **Traceability**: Easy to see which files belong together
3. **Comparison**: Compare outputs from different runs
4. **No Overwriting**: New runs don't overwrite previous analysis
5. **Status Tracking**: Each run has metadata showing success/failure

## Usage

### Running Processors

All processors automatically create or use the current run:

```bash
# First processor creates a new run
python process_uc.py

# Second processor uses the same run
python process_activities.py

# All outputs go to: Runs/run_YYYYMMDD_HHMMSS/
```

### Project Analysis

The project analysis script automatically creates a new run:

```bash
python run_project_analysis.py "/path/to/project/folder"

# Output: Runs/run_YYYYMMDD_HHMMSS/
#   - uc_processed.json
#   - milestone_activities_processed.json
#   - master_risk_report.json
```

### Listing Runs

View all analysis runs:

```bash
python list_runs.py
```

Output example:
```
================================================================================
📊 ANALYSIS RUNS
================================================================================

Total runs: 3

Run ID                    Status          Created At                Files
--------------------------------------------------------------------------------
run_20251125_160230       ✅ completed     2025-11-25 16:02:30       UC, Activity, Risk
run_20251125_151730       ⏳ in progress   2025-11-25 15:17:30       UC, Activity
run_20251125_143015       ❌ failed        2025-11-25 14:30:15       UC

================================================================================
Latest successful run: run_20251125_160230
Location: Runs/run_20251125_160230
================================================================================
```

### Accessing Run Data

```python
from run_manager import get_current_run_id, get_run_output_dir, get_latest_successful_run

# Get current run
run_id = get_current_run_id()
run_dir = get_run_output_dir()

# Load data from current run
import json
with open(run_dir / "uc_processed.json") as f:
    uc_data = json.load(f)

# Get latest successful run
latest_id, latest_dir = get_latest_successful_run()
```

## Run Metadata

Each run has a `run_metadata.json` file:

```json
{
    "run_id": "run_20251125_151730",
    "created_at": "2025-11-25T15:17:30.321514",
    "status": "in_progress",
    "completed_at": "2025-11-25T15:18:45.123456"
}
```

**Status values:**
- `in_progress`: Run is currently being processed
- `completed`: Run finished successfully
- `failed`: Run encountered an error

## Backward Compatibility

For compatibility with existing scripts, processors also save a copy to the legacy `Data/` directory:

```
Data/
├── uc_processed.json                      # Latest UC output (legacy)
├── milestone_activities_processed.json    # Latest Activity output (legacy)
└── ...
```

This ensures that scripts expecting files in `Data/` continue to work.

## API Reference

### `create_new_run()`
Creates a new run with a unique timestamp-based ID.

**Returns:** `(run_id, run_dir_path)`

### `get_current_run_id()`
Gets the ID of the currently active run.

**Returns:** `run_id` string or `None`

### `get_run_output_dir(run_id=None)`
Gets the output directory for a run.

**Args:** `run_id` (optional, uses current if not specified)

**Returns:** `Path` object

### `mark_run_complete(run_id=None, success=True)`
Marks a run as completed or failed.

**Args:** 
- `run_id` (optional, uses current if not specified)
- `success` (boolean)

### `list_all_runs()`
Lists all runs in chronological order.

**Returns:** List of `(run_id, metadata_dict)` tuples

### `get_latest_successful_run()`
Gets the most recent successful run.

**Returns:** `(run_id, run_dir_path)` or `(None, None)`

## Best Practices

1. **Always create a new run** for a complete analysis cycle
2. **Mark runs as complete** when finished to help track success
3. **Use run IDs** in logs and reports for traceability
4. **Periodically clean old runs** to save disk space
5. **Document** what each run was analyzing in commit messages or notes

## Example: Complete Analysis Workflow

```python
from run_manager import create_new_run, mark_run_complete
import subprocess

# Create a new run
run_id, run_dir = create_new_run()
print(f"Starting analysis run: {run_id}")

try:
    # Run all processors
    subprocess.run(["python", "process_uc.py"], check=True)
    subprocess.run(["python", "process_activities.py"], check=True)
    subprocess.run(["python", "run_risk_analysis.py"], check=True)
    
    # Mark as successful
    mark_run_complete(run_id, success=True)
    print(f"✅ Analysis complete: {run_dir}")
    
except Exception as e:
    # Mark as failed
    mark_run_complete(run_id, success=False)
    print(f"❌ Analysis failed: {e}")
```

## Migration Notes

### For Existing Scripts

If you have scripts that read from `Data/`:

**Option 1:** Continue using legacy files (no changes needed)
```python
# Still works - reads latest output
with open("Data/uc_processed.json") as f:
    data = json.load(f)
```

**Option 2:** Update to use run manager
```python
from run_manager import get_latest_successful_run

# Read from specific run
run_id, run_dir = get_latest_successful_run()
with open(run_dir / "uc_processed.json") as f:
    data = json.load(f)
```
