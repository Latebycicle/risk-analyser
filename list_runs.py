#!/usr/bin/env python3
"""
List all analysis runs and their status.

Usage: python list_runs.py
"""

from run_manager import list_all_runs, get_latest_successful_run
from pathlib import Path
import json

def main():
    print("="*80)
    print("📊 ANALYSIS RUNS")
    print("="*80)
    print()
    
    runs = list_all_runs()
    
    if not runs:
        print("No runs found.")
        return
    
    print(f"Total runs: {len(runs)}\n")
    print(f"{'Run ID':<25} {'Status':<15} {'Created At':<25} {'Files'}")
    print("-"*80)
    
    for run_id, metadata in reversed(runs):  # Most recent first
        status = metadata.get("status", "unknown")
        created_at = metadata.get("created_at", "N/A")
        
        # Format created_at for display
        if created_at != "N/A":
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at)
                created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        # Check what files exist in the run
        run_dir = Path("Runs") / run_id
        files = []
        if (run_dir / "uc_processed.json").exists():
            files.append("UC")
        if (run_dir / "milestone_activities_processed.json").exists():
            files.append("Activity")
        if (run_dir / "master_risk_report.json").exists():
            files.append("Risk")
        
        files_str = ", ".join(files) if files else "None"
        
        # Status emoji
        if status == "completed":
            status_display = "✅ completed"
        elif status == "failed":
            status_display = "❌ failed"
        elif status == "in_progress":
            status_display = "⏳ in progress"
        else:
            status_display = f"❓ {status}"
        
        print(f"{run_id:<25} {status_display:<15} {created_at:<25} {files_str}")
    
    print()
    print("="*80)
    
    # Show latest successful run
    latest_id, latest_dir = get_latest_successful_run()
    if latest_id:
        print(f"Latest successful run: {latest_id}")
        print(f"Location: {latest_dir}")
    else:
        print("No successful runs found.")
    
    print("="*80)


if __name__ == "__main__":
    main()
