"""
Run Manager - Handles unique run IDs and output directories

This module provides utilities to create unique run directories for each analysis run,
ensuring that all processor outputs are grouped together in timestamped folders.

Usage:
    from src.run_manager import get_current_run_id, get_run_output_dir, create_new_run
    
    run_id, run_dir = create_new_run()
    output_file = run_dir / "uc_processed.json"
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import RUNS_DIR
except ImportError:
    RUNS_DIR = PROJECT_ROOT / "runs"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Ensure runs directory exists
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# File to track current run ID
CURRENT_RUN_FILE = RUNS_DIR / ".current_run"


def create_new_run():
    """
    Create a new run with a unique timestamp-based ID.
    
    Returns:
        Tuple of (run_id, run_dir_path)
    """
    # Generate run ID based on timestamp (YYYY-MM-DD_HH-MM-SS format)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_id = f"run_{timestamp}"
    
    # Create run directory
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(exist_ok=True)
    
    # Save run metadata
    metadata = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "status": "in_progress"
    }
    
    metadata_file = run_dir / "run_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Set as current run
    with open(CURRENT_RUN_FILE, "w") as f:
        f.write(run_id)
    
    logging.info(f"Created new run: {run_id}")
    
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
    
    run_dir = RUNS_DIR / run_id
    
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
    
    run_dir = RUNS_DIR / run_id
    metadata_file = run_dir / "run_metadata.json"
    
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        metadata["status"] = "completed" if success else "failed"
        metadata["completed_at"] = datetime.now().isoformat()
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        status_str = "✅ COMPLETED" if success else "❌ FAILED"
        logging.info(f"Run {run_id}: {status_str}")


def list_all_runs():
    """
    List all runs in chronological order.
    
    Returns:
        List of tuples: (run_id, metadata_dict)
    """
    runs = []
    
    for run_dir in sorted(RUNS_DIR.iterdir()):
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
        Tuple of (run_id, run_dir_path) or (None, None) if none found
    """
    all_runs = list_all_runs()
    
    successful_runs = [
        (run_id, metadata) 
        for run_id, metadata in all_runs 
        if metadata.get("status") == "completed"
    ]
    
    if not successful_runs:
        return None, None
    
    successful_runs.sort(
        key=lambda x: x[1].get("created_at", ""), 
        reverse=True
    )
    
    latest_run_id = successful_runs[0][0]
    latest_run_dir = RUNS_DIR / latest_run_id
    
    return latest_run_id, latest_run_dir


if __name__ == "__main__":
    print("=" * 70)
    print("RUN MANAGER - Demo")
    print("=" * 70)
    
    run_id, run_dir = create_new_run()
    print(f"\n✓ Created run: {run_id}")
    print(f"  Directory: {run_dir}")
    
    print("\n✓ All runs:")
    for rid, metadata in list_all_runs():
        status = metadata.get("status", "unknown")
        print(f"  - {rid}: {status}")
    
    print("\n" + "=" * 70)
