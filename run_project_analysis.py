#!/usr/bin/env python3
"""
Run Risk Analysis on Any Project Folder

This script processes any project folder and runs complete risk analysis.
All outputs go to a timestamped run directory - NO Data/ folder dependency.

Usage: python run_project_analysis.py <project_folder_path>

Architecture:
    1. Identify project files using ProjectLoader
    2. Create timestamped run directory
    3. Run processors directly on source files → output to run_dir
    4. Run risk analysis on run_dir data
    5. Generate report in run_dir
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.project_loader import ProjectLoader
from src.run_manager import create_new_run, mark_run_complete

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_analysis_for_project(project_path):
    """
    Run complete risk analysis for a project folder.
    
    All outputs go directly to run_dir - no intermediate Data/ folder.
    
    Steps:
    1. Identify project files using ProjectLoader
    2. Create timestamped run directory
    3. Run UC processor → output to run_dir
    4. Run Activity processor → output to run_dir
    5. Run Billing processor (if available) → output to run_dir
    6. Run risk analysis on run_dir data
    """
    
    project_path = Path(project_path)
    if not project_path.exists():
        raise ValueError(f"Project folder not found: {project_path}")
    
    # Create a new run directory
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
        uc_path = Path(files['uc'])
        print(f"  UC File      : ✓ {uc_path.name}")
    else:
        print(f"  UC File      : ✗ NOT FOUND (Required)")
        return False
        
    if files['activity']:
        activity_path = Path(files['activity'])
        print(f"  Activity File: ✓ {activity_path.name}")
    else:
        print(f"  Activity File: ✗ NOT FOUND (Required)")
        return False
        
    if files['billing']:
        billing_path = Path(files['billing'])
        print(f"  Billing File : ✓ {billing_path.name}")
    else:
        print(f"  Billing File : ⚠ Not found (Optional - Fallback Mode will be used)")
        billing_path = None
    
    print(f"  Context Files: {len(files['context'])} additional files")
    print()
    
    # Convert to Path objects
    uc_path = Path(files['uc'])
    activity_path = Path(files['activity'])
    billing_path = Path(files['billing']) if files['billing'] else None
    
    # Save file inventory to run directory
    file_inventory = {
        'project_path': str(project_path),
        'uc': str(uc_path),
        'activity': str(activity_path),
        'billing': str(billing_path) if billing_path else None,
        'context': [str(Path(f)) for f in files['context']],
        'analyzed_at': datetime.now().isoformat()
    }
    
    file_inventory_path = run_dir / 'file_inventory.json'
    with open(file_inventory_path, 'w', encoding='utf-8') as f:
        json.dump(file_inventory, f, indent=2)
    logging.info(f"Saved file inventory to: {file_inventory_path}")
    
    # Step 2: Run UC Processor
    print()
    logging.info("Step 2: Running UC processor...")
    try:
        from src.process_uc import process_uc_file, save_uc_data
        uc_data = process_uc_file(uc_path)
        save_uc_data(uc_data, run_dir)
        print("  ✓ UC data processed and saved")
    except Exception as e:
        logging.error(f"UC processor failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Run Activity Processor
    logging.info("Step 3: Running Activity processor...")
    try:
        from src.process_activities import process_activities_file, save_activities_data
        activity_data = process_activities_file(activity_path)
        save_activities_data(activity_data, run_dir)
        print("  ✓ Activity data processed and saved")
    except Exception as e:
        logging.error(f"Activity processor failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Run Billing Processor (if available)
    if billing_path:
        logging.info("Step 4: Running Billing processor...")
        try:
            from src.process_billing import process_billing_file, save_billing_data
            
            # Extract reference months from UC data for smart date inference
            reference_months = list(uc_data.get('monthly_data', {}).keys())
            logging.info(f"  Reference months for date inference: {reference_months[:3]}...{reference_months[-1] if reference_months else ''}")
            
            billing_data = process_billing_file(billing_path, reference_months=reference_months)
            save_billing_data(billing_data, run_dir)
            print("  ✓ Billing data processed and saved")
        except Exception as e:
            logging.warning(f"Billing processor failed: {e}")
            print("  ⚠ Billing processor failed - will use Fallback Mode")
    else:
        logging.info("Step 4: Skipping Billing processor (no billing file)")
        print("  ⏭️  Skipping billing - will use Fallback Mode")
    
    print()
    
    # Step 5: Run Risk Analysis
    logging.info("Step 5: Running risk analysis...")
    try:
        from src.run_risk_analysis import run_analysis
        
        # Load company context if available
        company_context = ""
        for context_file in files['context']:
            if 'context' in Path(context_file).name.lower():
                try:
                    with open(context_file, 'r', encoding='utf-8') as f:
                        company_context = f.read()
                    break
                except:
                    pass
        
        result = run_analysis(
            run_dir=run_dir,
            company_context=company_context,
            activity_excel=activity_path
        )
        
        if result != 0:
            logging.error("Risk analysis failed")
            return False
            
    except Exception as e:
        logging.error(f"Risk analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("="*70)
    print("✅ ANALYSIS COMPLETE!")
    print("="*70)
    print(f"Run ID: {run_id}")
    print(f"Output Directory: {run_dir}")
    print()
    print("Generated files:")
    for f in sorted(run_dir.iterdir()):
        print(f"  - {f.name}")
    print("="*70)
    
    # Mark run as complete
    mark_run_complete(run_id, success=True)
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_project_analysis.py <project_folder_path>")
        print("\nExample:")
        print("  python run_project_analysis.py '/path/to/project/folder'")
        print("\nThe script will:")
        print("  1. Auto-detect UC, Activity, and Billing files in the folder")
        print("  2. Process them and run risk analysis")
        print("  3. Output everything to a timestamped Runs/ directory")
        print("\n⚠️  No Data/ folder is used - all outputs go to Runs/")
        sys.exit(1)
    
    project_path = sys.argv[1]
    success = run_analysis_for_project(project_path)
    
    sys.exit(0 if success else 1)
