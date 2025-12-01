import os
import shutil
from datetime import datetime

# 1. Setup Archive Folder
archive_dir = "archive"
if not os.path.exists(archive_dir):
    os.makedirs(archive_dir)
    print(f"✅ Created '{archive_dir}' directory.")

# 2. List of files that are now redundant (because they live in src/)
# OR are dead code identified in your summary.
files_to_move = [
    # The Old Processors (Now in src/)
    "process_uc.py",
    "process_billing.py",
    "process_activities.py",
    "run_risk_analysis.py",
    "generate_report.py",
    "compliance_checker.py",
    "metadata_extractor.py",
    "project_loader.py",
    
    # The Dead Code (Identified in summary)
    "test_system.py",
    "list_runs.py",
    "project_loader_examples.md",
    
    # The One-Time Setup Script (Job done)
    "refactor_project.py" 
]

# 3. Move the files
print(f"\n📦 Moving files to {archive_dir}...")
count = 0

for filename in files_to_move:
    if os.path.exists(filename):
        # Add timestamp to filename if destination already exists to avoid overwrite
        destination = os.path.join(archive_dir, filename)
        if os.path.exists(destination):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(filename)
            destination = os.path.join(archive_dir, f"{base}_{timestamp}{ext}")
            
        shutil.move(filename, destination)
        print(f"  -> Moved: {filename}")
        count += 1
    else:
        print(f"  X Skipped: {filename} (Not found in root)")

print(f"\n✨ Cleanup Complete! Moved {count} files.")
print("   You can now safely delete the 'archive_old_files.py' script.")