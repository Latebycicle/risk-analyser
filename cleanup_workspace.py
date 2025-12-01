#!/usr/bin/env python3
"""
Cleanup Workspace Script
Moves legacy root-level files to archive/ directory after refactoring.
"""

import os
import shutil
from pathlib import Path

# Files to move to archive
LEGACY_FILES = [
    # Core processors (now in src/)
    "process_uc.py",
    "process_billing.py",
    "process_activities.py",
    "run_risk_analysis.py",
    "generate_report.py",
    "compliance_checker.py",
    "metadata_extractor.py",
    "project_loader.py",
    "run_manager.py",
    
    # Dead code / utilities
    "test_system.py",
    "list_runs.py",
    "project_loader_examples.md",
    
    # Refactoring scripts (no longer needed)
    "refactor_project.py",
    "archive_old_files.py",
]

def main():
    """Move legacy files to archive directory."""
    # Get current directory
    root_dir = Path(__file__).parent.resolve()
    archive_dir = root_dir / "archive"
    
    print("=" * 50)
    print("WORKSPACE CLEANUP")
    print("=" * 50)
    print(f"Root directory: {root_dir}")
    print(f"Archive directory: {archive_dir}")
    print()
    
    # Create archive directory
    archive_dir.mkdir(exist_ok=True)
    print(f"✓ Archive directory ready")
    print()
    
    # Track results
    moved = []
    skipped = []
    errors = []
    
    print("Processing files:")
    print("-" * 40)
    
    for filename in LEGACY_FILES:
        source = root_dir / filename
        dest = archive_dir / filename
        
        if not source.exists():
            print(f"  Skipping {filename} (not found)")
            skipped.append(filename)
            continue
        
        try:
            # Handle if destination already exists
            if dest.exists():
                dest.unlink()
            
            shutil.move(str(source), str(dest))
            print(f"  ✓ Moved {filename}")
            moved.append(filename)
        except Exception as e:
            print(f"  ✗ Error moving {filename}: {e}")
            errors.append((filename, str(e)))
    
    # Summary
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  Moved:   {len(moved)} files")
    print(f"  Skipped: {len(skipped)} files (not found)")
    print(f"  Errors:  {len(errors)} files")
    
    if moved:
        print()
        print("Moved files:")
        for f in moved:
            print(f"  - {f}")
    
    if errors:
        print()
        print("Errors:")
        for f, e in errors:
            print(f"  - {f}: {e}")
    
    print()
    print("✓ Cleanup complete!")
    print()
    print("Next steps:")
    print("  1. Test: python -m src.run_risk_analysis")
    print("  2. If all works, you can delete archive/ later")
    
    return len(errors) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
