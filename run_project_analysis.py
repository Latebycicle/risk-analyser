#!/usr/bin/env python3
"""
Run Risk Analysis on Any Project Folder

This script processes any project folder and runs complete risk analysis.
Usage: python run_project_analysis.py <project_folder_path>
"""

import sys
import json
import shutil
from pathlib import Path
from project_loader import ProjectLoader
import subprocess
import logging
from run_manager import create_new_run, mark_run_complete, get_run_output_dir

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_analysis_for_project(project_path):
    """
    Run complete risk analysis for a project folder.
    
    Steps:
    1. Identify project files using ProjectLoader
    2. Copy files to Data/ directory
    3. Update processor configurations
    4. Run UC processor (process_uc.py)
    5. Run Activity processor (process_activities.py)
    6. Run Billing processor if available (process_billing.py)
    7. Run risk analysis (run_risk_analysis.py)
    8. Generate report (generate_report.py)
    """
    
    project_path = Path(project_path)
    if not project_path.exists():
        raise ValueError(f"Project folder not found: {project_path}")
    
    # Create a new run
    run_id, run_dir = create_new_run()
    
    print("="*70)
    print(f"🔍 ANALYZING PROJECT: {project_path.name}")
    print("="*70)
    print(f"Path: {project_path}")
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print()
    
    # Step 1: Identify files
    logging.info("Step 1: Identifying project files...")
    loader = ProjectLoader(project_path)
    files = loader.identify_files()
    
    print("📁 Identified Files:")
    print("-"*70)
    if files['uc']:
        uc_path = Path(files['uc']) if isinstance(files['uc'], str) else files['uc']
        print(f"  UC File      : ✓ {uc_path.name}")
    else:
        print(f"  UC File      : ✗ NOT FOUND (Required)")
        return False
        
    if files['activity']:
        activity_path = Path(files['activity']) if isinstance(files['activity'], str) else files['activity']
        print(f"  Activity File: ✓ {activity_path.name}")
    else:
        print(f"  Activity File: ✗ NOT FOUND (Required)")
        return False
        
    if files['billing']:
        billing_path = Path(files['billing']) if isinstance(files['billing'], str) else files['billing']
        print(f"  Billing File : ✓ {billing_path.name}")
    else:
        print(f"  Billing File : ⚠ Not found (Optional)")
        billing_path = None
    
    print(f"  Context Files: {len(files['context'])} additional files")
    print()
    
    # Convert to Path objects for consistency
    uc_path = Path(files['uc'])
    activity_path = Path(files['activity'])
    billing_path = Path(files['billing']) if files['billing'] else None
    
    # Save file inventory for report generation
    file_inventory = {
        'uc': str(uc_path),
        'activity': str(activity_path),
        'billing': str(billing_path) if billing_path else None,
        'context': [str(Path(f)) for f in files['context']]
    }
    
    # Step 2: Copy files to Data directory
    logging.info("Step 2: Copying files to Data/ directory...")
    data_dir = Path("Data")
    data_dir.mkdir(exist_ok=True)
    
    # Backup existing data
    backup_dir = Path("Data_Backup")
    if data_dir.exists():
        logging.info("  Creating backup of existing Data/ folder...")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(data_dir, backup_dir, dirs_exist_ok=True)
    
    # Copy UC file
    uc_dest = data_dir / uc_path.name
    shutil.copy2(uc_path, uc_dest)
    logging.info(f"  Copied: {uc_path.name}")
    
    # Copy Activity file
    activity_dest = data_dir / activity_path.name
    shutil.copy2(activity_path, activity_dest)
    logging.info(f"  Copied: {activity_path.name}")
    
    # Copy Billing file if exists
    if billing_path:
        billing_dest = data_dir / billing_path.name
        shutil.copy2(billing_path, billing_dest)
        logging.info(f"  Copied: {billing_path.name}")
    
    # Save file inventory to Data directory for report generation
    file_inventory_path = data_dir / 'file_inventory.json'
    with open(file_inventory_path, 'w', encoding='utf-8') as f:
        json.dump(file_inventory, f, indent=2)
    logging.info("  Saved file inventory")
    
    print()
    
    # Step 3: Update processor configurations
    logging.info("Step 3: Updating processor configurations...")
    
    # Update process_uc.py
    update_process_uc_config(uc_dest.name)
    
    # Update process_activities.py
    update_process_activities_config(activity_dest.name)
    
    # Update process_billing.py if needed
    if billing_path:
        update_process_billing_config(billing_dest.name)
    
    print()
    
    # Step 4: Run processors
    python_exe = sys.executable
    
    logging.info("Step 4: Running UC processor...")
    result = subprocess.run([python_exe, "process_uc.py"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"UC processor failed: {result.stderr}")
        return False
    print(result.stdout)
    
    logging.info("Step 5: Running Activity processor...")
    result = subprocess.run([python_exe, "process_activities.py"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Activity processor failed: {result.stderr}")
        return False
    print(result.stdout)
    
    if billing_path:
        logging.info("Step 6: Running Billing processor...")
        result = subprocess.run([python_exe, "process_billing.py"], capture_output=True, text=True)
        if result.returncode != 0:
            logging.warning(f"Billing processor failed: {result.stderr}")
    
    print()
    
    # Step 7: Run risk analysis
    logging.info("Step 7: Running risk analysis...")
    result = subprocess.run([python_exe, "run_risk_analysis.py"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Risk analysis failed: {result.stderr}")
        return False
    print(result.stdout)
    
    print()
    
    # Step 8: Generate report
    logging.info("Step 8: Generating report...")
    result = subprocess.run([python_exe, "generate_report.py"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Report generation failed: {result.stderr}")
        return False
    print(result.stdout)
    
    print()
    print("="*70)
    print("✅ ANALYSIS COMPLETE!")
    print("="*70)
    print(f"Run ID: {run_id}")
    print(f"Output Directory: {run_dir}")
    print(f"  - uc_processed.json")
    print(f"  - milestone_activities_processed.json")
    print(f"  - master_risk_report.json (if generated)")
    print(f"Report location: Report/Project_Risk_Report.md")
    print("="*70)
    
    # Mark run as complete
    mark_run_complete(run_id, success=True)
    
    return True


def update_process_uc_config(filename):
    """Update EXCEL_FILE in process_uc.py"""
    with open("process_uc.py", "r") as f:
        content = f.read()
    
    # Replace EXCEL_FILE line
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith("EXCEL_FILE = "):
            lines[i] = f"EXCEL_FILE = 'Data/{filename}'"
            break
    
    with open("process_uc.py", "w") as f:
        f.write('\n'.join(lines))
    
    logging.info(f"  Updated process_uc.py: EXCEL_FILE = 'Data/{filename}'")


def update_process_activities_config(filename):
    """Update EXCEL_FILE in process_activities.py"""
    with open("process_activities.py", "r") as f:
        content = f.read()
    
    # Replace EXCEL_FILE line
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith("EXCEL_FILE = "):
            lines[i] = f"EXCEL_FILE = 'Data/{filename}'"
            break
    
    with open("process_activities.py", "w") as f:
        f.write('\n'.join(lines))
    
    logging.info(f"  Updated process_activities.py: EXCEL_FILE = 'Data/{filename}'")


def update_process_billing_config(filename):
    """Update EXCEL_FILE in process_billing.py"""
    try:
        with open("process_billing.py", "r") as f:
            content = f.read()
        
        # Replace EXCEL_FILE line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith("EXCEL_FILE = "):
                lines[i] = f"EXCEL_FILE = 'Data/{filename}'"
                break
        
        with open("process_billing.py", "w") as f:
            f.write('\n'.join(lines))
        
        logging.info(f"  Updated process_billing.py: EXCEL_FILE = 'Data/{filename}'")
    except FileNotFoundError:
        logging.warning("  process_billing.py not found, skipping...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_project_analysis.py <project_folder_path>")
        print("\nExample:")
        print("  python run_project_analysis.py '/Users/akhilr/Documents/Sambhav Foundation/Projects/TataBluescope'")
        sys.exit(1)
    
    project_path = sys.argv[1]
    success = run_analysis_for_project(project_path)
    
    sys.exit(0 if success else 1)
