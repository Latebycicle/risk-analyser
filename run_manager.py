"""
Run Manager - Handles unique run IDs and output directories

This module provides utilities to create unique run directories for each analysis run,
ensuring that all processor outputs (UC, Activity, Billing) are grouped together.

Usage:
    from run_manager import get_current_run_id, get_run_output_dir
    
    run_id = get_current_run_id()
    output_dir = get_run_output_dir()
    
    # Save your processed data
    output_file = output_dir / "uc_processed.json"
"""

import json
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Base directory for all runs
RUNS_BASE_DIR = Path("Runs")
RUNS_BASE_DIR.mkdir(exist_ok=True)

# File to track current run ID
CURRENT_RUN_FILE = RUNS_BASE_DIR / ".current_run"


def create_new_run():
    """
    Create a new run with a unique ID.
    
    Returns:
        Tuple of (run_id, run_dir_path)
    """
    # Generate run ID based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}"
    
    # Create run directory
    run_dir = RUNS_BASE_DIR / run_id
    run_dir.mkdir(exist_ok=True)
    
    # Save run metadata
    metadata = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "status": "in_progress"
    }
    
    metadata_file = run_dir / "run_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=4)
    
    # Set as current run
    with open(CURRENT_RUN_FILE, "w") as f:
        f.write(run_id)
    
    logging.info(f"Created new run: {run_id}")
    logging.info(f"Output directory: {run_dir}")
    
    return run_id, run_dir


def get_current_run_id():
    """
    Get the current active run ID.
    
    Returns:
        Current run ID string, or None if no run is active
    """
    if not CURRENT_RUN_FILE.exists():
        return None
    
    with open(CURRENT_RUN_FILE, "r") as f:
        return f.read().strip()


def get_run_output_dir(run_id=None):
    """
    Get the output directory for a specific run.
    
    Args:
        run_id: Optional run ID. If None, uses current run.
        
    Returns:
        Path object for the run directory
    """
    if run_id is None:
        run_id = get_current_run_id()
    
    if run_id is None:
        raise ValueError("No active run. Call create_new_run() first.")
    
    run_dir = RUNS_BASE_DIR / run_id
    
    if not run_dir.exists():
        raise ValueError(f"Run directory does not exist: {run_dir}")
    
    return run_dir


def mark_run_complete(run_id=None, success=True):
    """
    Mark a run as complete.
    
    Args:
        run_id: Optional run ID. If None, uses current run.
        success: Whether the run completed successfully
    """
    if run_id is None:
        run_id = get_current_run_id()
    
    if run_id is None:
        logging.warning("No active run to mark complete")
        return
    
    run_dir = RUNS_BASE_DIR / run_id
    metadata_file = run_dir / "run_metadata.json"
    
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        metadata["status"] = "completed" if success else "failed"
        metadata["completed_at"] = datetime.now().isoformat()
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=4)
        
        status_str = "✅ COMPLETED" if success else "❌ FAILED"
        logging.info(f"Run {run_id}: {status_str}")


def list_all_runs():
    """
    List all runs in chronological order.
    
    Returns:
        List of tuples: (run_id, metadata_dict)
    """
    runs = []
    
    for run_dir in sorted(RUNS_BASE_DIR.iterdir()):
        if run_dir.is_dir() and run_dir.name.startswith("run_"):
            metadata_file = run_dir / "run_metadata.json"
            
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                runs.append((run_dir.name, metadata))
            else:
                runs.append((run_dir.name, {"status": "unknown"}))
    
    return runs


def get_latest_successful_run():
    """
    Get the most recent successful run.
    
    Returns:
        Tuple of (run_id, run_dir_path) or (None, None) if no successful runs
    """
    all_runs = list_all_runs()
    
    # Filter successful runs and sort by creation time (newest first)
    successful_runs = [
        (run_id, metadata) 
        for run_id, metadata in all_runs 
        if metadata.get("status") == "completed"
    ]
    
    if not successful_runs:
        return None, None
    
    # Sort by created_at timestamp (newest first)
    successful_runs.sort(
        key=lambda x: x[1].get("created_at", ""), 
        reverse=True
    )
    
    latest_run_id = successful_runs[0][0]
    latest_run_dir = RUNS_BASE_DIR / latest_run_id
    
    return latest_run_id, latest_run_dir


if __name__ == "__main__":
    # Demo usage
    print("=" * 70)
    print("RUN MANAGER - Demo")
    print("=" * 70)
    
    # Create a new run
    run_id, run_dir = create_new_run()
    print(f"\n✓ Created run: {run_id}")
    print(f"  Directory: {run_dir}")
    
    # Check current run
    current = get_current_run_id()
    print(f"\n✓ Current run: {current}")
    
    # List all runs
    print("\n✓ All runs:")
    for rid, metadata in list_all_runs():
        status = metadata.get("status", "unknown")
        print(f"  - {rid}: {status}")
    
    print("\n" + "=" * 70)
