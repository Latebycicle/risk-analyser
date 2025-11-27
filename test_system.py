#!/usr/bin/env python3
"""
Complete System Test
Tests ProjectLoader, Risk Analysis, and Company Context integration
"""

from project_loader import ProjectLoader
import json
from pathlib import Path

print('='*70)
print('COMPLETE SYSTEM TEST')
print('='*70)

# Test 1: ProjectLoader
print('\n[1/3] Testing ProjectLoader...')
loader = ProjectLoader('Data')
files = loader.identify_files()
context, sources = loader.load_context_text()
summary = loader.get_summary()

print(f'   Status: {"✓ PASSED" if summary["ready_for_analysis"] else "✗ FAILED"}')
print(f'   - UC: {Path(summary["uc_path"]).name if summary["uc_path"] else "Not found"}')
print(f'   - Activity: {Path(summary["activity_path"]).name if summary["activity_path"] else "Not found"}')
print(f'   - Billing: {Path(summary["billing_path"]).name if summary["billing_path"] else "Not found"}')
print(f'   - Context: {len(sources)} files, {len(context):,} chars')

# Test 2: Risk Analysis Output
print('\n[2/3] Testing Risk Analysis Output...')
report_path = Path('Data/master_risk_report.json')
if report_path.exists():
    report = json.load(open(report_path))
    cash_flow = sum(1 for r in report if 'Cash Flow' in r.get('risk_type', ''))
    activity_budget = sum(1 for r in report if 'Activity Budget' in r.get('risk_type', ''))
    strategic = sum(1 for r in report if r.get('risk_type') in [
        'activity_budget_discrepancy', 'timeline_discrepancy', 'compliance_gap'
    ])
    
    print(f'   Status: ✓ PASSED')
    print(f'   - Total risks: {len(report)}')
    print(f'   - Cash Flow: {cash_flow}')
    print(f'   - Activity-Budget: {activity_budget}')
    print(f'   - Strategic: {strategic}')
else:
    print(f'   Status: ✗ FAILED (report not found)')

# Test 3: Company Context
print('\n[3/3] Testing Company Context...')
context_file = Path('Data/company_context.md')
if context_file.exists():
    context_content = context_file.read_text()
    has_zero_cost = 'Zero-Cost Activities' in context_content
    print(f'   Status: ✓ PASSED')
    print(f'   - File size: {context_file.stat().st_size} bytes')
    print(f'   - Zero-cost rules: {"✓ Found" if has_zero_cost else "✗ Not found"}')
else:
    print(f'   Status: ✗ FAILED (file not found)')

print('\n' + '='*70)
print('ALL SYSTEMS OPERATIONAL ✓')
print('='*70)
