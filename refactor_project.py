#!/usr/bin/env python3
"""
Project Refactoring Script

This script reorganizes the risk-analyser project into a clean folder structure:
- src/: All Python modules
- config/: Configuration files
- data/: Input Excel/PDF files (renamed from Data/)
- runs/: Output logs, JSONs, and reports (renamed from Runs/)

Run: python refactor_project.py
"""

import os
import shutil
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Define the new folder structure
NEW_STRUCTURE = {
    'src': [
        'process_uc.py',
        'process_billing.py',
        'process_activities.py',
        'run_risk_analysis.py',
        'generate_report.py',
        'compliance_checker.py',
        'metadata_extractor.py',
        'project_loader.py',
        'run_manager.py',
    ],
    'config': [],  # Will create settings.py separately
    'data': [],     # Will move Data/ contents
    'runs': [],     # Will move Runs/ contents
}

# Files that are potentially dead code or redundant
DEAD_CODE_FILES = [
    'test_system.py',      # Test file - not part of main workflow
    'list_runs.py',        # Utility script - not called by run_risk_analysis.py
    'project_loader_examples.md',  # Documentation file
]

# Files to keep in root (entry points, documentation)
ROOT_FILES = [
    'readme.md',
    'RUN_MANAGEMENT.md',
    'TODO.md',
]


def create_directories():
    """Create the new directory structure."""
    print("=" * 60)
    print("Creating directory structure...")
    print("=" * 60)
    
    for folder in ['src', 'config', 'data', 'runs']:
        folder_path = PROJECT_ROOT / folder
        folder_path.mkdir(exist_ok=True)
        print(f"  ✓ Created: {folder}/")


def move_source_files():
    """Move Python source files to src/ directory."""
    print("\n" + "=" * 60)
    print("Moving source files to src/...")
    print("=" * 60)
    
    for filename in NEW_STRUCTURE['src']:
        src_path = PROJECT_ROOT / filename
        dst_path = PROJECT_ROOT / 'src' / filename
        
        if src_path.exists():
            # Don't overwrite if destination exists
            if dst_path.exists():
                print(f"  ⊗ Skipped (already exists): {filename}")
            else:
                shutil.copy2(src_path, dst_path)
                print(f"  ✓ Copied: {filename} → src/{filename}")
        else:
            print(f"  ⚠ Not found: {filename}")


def move_data_folder():
    """Move Data/ contents to data/ directory."""
    print("\n" + "=" * 60)
    print("Moving Data/ contents to data/...")
    print("=" * 60)
    
    old_data = PROJECT_ROOT / 'Data'
    new_data = PROJECT_ROOT / 'data'
    
    if old_data.exists():
        for item in old_data.iterdir():
            dst = new_data / item.name
            if not dst.exists():
                if item.is_file():
                    shutil.copy2(item, dst)
                else:
                    shutil.copytree(item, dst)
                print(f"  ✓ Copied: Data/{item.name} → data/{item.name}")
            else:
                print(f"  ⊗ Skipped (already exists): {item.name}")
    else:
        print("  ⚠ Data/ folder not found")


def move_runs_folder():
    """Move Runs/ contents to runs/ directory."""
    print("\n" + "=" * 60)
    print("Moving Runs/ contents to runs/...")
    print("=" * 60)
    
    old_runs = PROJECT_ROOT / 'Runs'
    new_runs = PROJECT_ROOT / 'runs'
    
    if old_runs.exists():
        for item in old_runs.iterdir():
            dst = new_runs / item.name
            if not dst.exists():
                if item.is_file():
                    shutil.copy2(item, dst)
                else:
                    shutil.copytree(item, dst)
                print(f"  ✓ Copied: Runs/{item.name} → runs/{item.name}")
            else:
                print(f"  ⊗ Skipped (already exists): {item.name}")
    else:
        print("  ⚠ Runs/ folder not found")


def identify_dead_code():
    """Identify and list potentially dead code files."""
    print("\n" + "=" * 60)
    print("Dead Code Analysis")
    print("=" * 60)
    
    print("\nThe following files are NOT called by run_risk_analysis.py")
    print("and may be candidates for removal or archiving:\n")
    
    for filename in DEAD_CODE_FILES:
        filepath = PROJECT_ROOT / filename
        if filepath.exists():
            print(f"  ⚠ {filename}")
            # Get first line of file for context
            try:
                with open(filepath, 'r') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('#') or first_line.startswith('"""'):
                        print(f"      └─ {first_line[:60]}...")
            except:
                pass
        else:
            print(f"  ⊗ {filename} (not found)")
    
    print("\nRecommendation: Move these to an 'archive/' folder or delete them.")


def create_init_files():
    """Create __init__.py files for the src/ package."""
    print("\n" + "=" * 60)
    print("Creating __init__.py files...")
    print("=" * 60)
    
    src_init = PROJECT_ROOT / 'src' / '__init__.py'
    src_init.write_text('"""Risk Analyser Source Package"""\n')
    print(f"  ✓ Created: src/__init__.py")
    
    config_init = PROJECT_ROOT / 'config' / '__init__.py'
    config_init.write_text('"""Risk Analyser Configuration Package"""\n')
    print(f"  ✓ Created: config/__init__.py")


def print_summary():
    """Print a summary of the refactoring."""
    print("\n" + "=" * 60)
    print("REFACTORING COMPLETE")
    print("=" * 60)
    
    print("""
New Project Structure:
    
    risk-analyser/
    ├── src/                    # Python source modules
    │   ├── __init__.py
    │   ├── process_uc.py       # UC processor (with date normalization)
    │   ├── process_billing.py  # Billing processor
    │   ├── process_activities.py
    │   ├── run_risk_analysis.py  # Main entry point
    │   ├── generate_report.py
    │   ├── compliance_checker.py
    │   ├── metadata_extractor.py
    │   ├── project_loader.py
    │   └── run_manager.py
    │
    ├── config/                 # Configuration
    │   ├── __init__.py
    │   └── settings.py         # All constants and file paths
    │
    ├── data/                   # Input files (Excel, PDF)
    │   └── [project files]
    │
    ├── runs/                   # Output (timestamped folders)
    │   └── run_YYYYMMDD_HHMMSS/
    │
    ├── readme.md
    ├── RUN_MANAGEMENT.md
    └── TODO.md

Next Steps:
1. Run: python config/settings.py (verify config loads)
2. Run: python -m src.run_risk_analysis (test new structure)
3. Delete old files in root once verified
4. Archive dead code files
""")


def main():
    """Main refactoring execution."""
    print("\n" + "=" * 60)
    print("RISK-ANALYSER PROJECT REFACTORING")
    print("=" * 60)
    print(f"\nProject Root: {PROJECT_ROOT}")
    
    # Step 1: Create directories
    create_directories()
    
    # Step 2: Move source files
    move_source_files()
    
    # Step 3: Move Data folder
    move_data_folder()
    
    # Step 4: Move Runs folder
    move_runs_folder()
    
    # Step 5: Create __init__.py files
    create_init_files()
    
    # Step 6: Identify dead code
    identify_dead_code()
    
    # Step 7: Print summary
    print_summary()


if __name__ == "__main__":
    main()
