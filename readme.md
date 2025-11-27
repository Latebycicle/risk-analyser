# Risk Analyzer

## Overview

Automated risk analysis system for project funding, budget utilization, and milestone compliance. Features adaptive UC (Utilization Certificate) processing that works with any Excel format.

## Key Features

### 1. Adaptive UC Processing
- **Automatic Column Detection**: Finds Budget Head, Vendor/Role, Cost Head, and monthly columns by searching for header keywords
- **Flexible Format Support**: Works with different UC Excel formats without code changes
- **Cost Head Tracking**: Captures granular budget allocations for accurate AI risk analysis

### 2. Multi-Layered Risk Analysis
- **Cash Flow Risk**: Detects months where spending exceeds available funding
- **Contractual Timeline Compliance**: AI-powered verification of billing dates
- **Activity-Budget Mapping**: Semantic matching of activities to budget lines using cost heads
- **Strategic Risk Audit**: Identifies contradictions between project narrative and financial reality

### 3. Comprehensive Reporting
- Markdown report with visualizations (charts, Gantt, cash flow tables)
- Dashboard statistics and risk severity breakdown
- Budget breakdown and category spending analysis

## Quick Start

### 1. Process Your UC File

Edit `process_uc.py` configuration:
```python
EXCEL_FILE = 'Data/YourUC.xlsx'
SHEET_NAME = 'Sheet1'

# If your UC uses different column names, add them here:
BUDGET_HEAD_KEYWORDS = ['budget head', 'budget', 'head']
COST_HEAD_KEYWORDS = ['cost head', 'cost', 'item']
```

Run:
```bash
python process_uc.py
```

### 2. Run Risk Analysis

```bash
python run_risk_analysis.py
```

### 3. Generate Report

```bash
python generate_report.py
```

Report will be saved to `Report/Project_Risk_Report.md`

## File Structure

- `process_uc.py` - Adaptive UC processor (finds columns by headers)
- `process_activities.py` - Milestone activities processor
- `process_billing.py` - Funding tranches processor
- `run_risk_analysis.py` - Main risk engine
- `generate_report.py` - Report generator with visualizations
- `compliance_checker.py` - AI-powered compliance checks
- `metadata_extractor.py` - Smart metadata extraction

## Adaptive UC Processing

The UC processor automatically detects columns by searching for keywords:

| Required Column | Keywords Searched |
|----------------|------------------|
| Budget Head | 'budget head', 'budget', 'head' |
| Vendor/Role | 'vendor', 'role', 'category' |
| Cost Head | 'cost head', 'cost', 'item' |
| Month Columns | 'plan' + month patterns |
| Total Column | 'plan total', 'total' |

The processor:
1. Searches first 3 rows for header keywords
2. Automatically detects where data rows begin
3. Aggregates budget lines by Budget Head + Vendor/Role
4. Tracks all cost heads under each budget line
5. Calculates monthly and cumulative spending

## Output JSON Structure

```json
{
  "budget_lines": {
    "Salary - Project Manager": {
      "budget_head": "Salary",
      "vendor_role_category": "Project Manager",
      "total": 480000.0,
      "monthly_plan": {"Apr-25": 0, "May-25": 60000, ...},
      "cost_heads": ["Program Manager"]
    }
  },
  "monthly_planned_spending": {...},
  "cumulative_planned_spending": {...}
}
```

## Requirements

- Python 3.x
- pandas
- matplotlib
- requests (for Ollama API)
- Ollama with qwen3:4b model

## Notes

- The system now tracks cost heads from column M for accurate budget allocation tracking
- AI risk analysis uses both budget lines and cost heads for semantic matching
- Supports multiple cost heads mapped to same budget line (e.g., "Trainer 1", "Trainer 2" → "Domain Trainer")

