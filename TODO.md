# Risk Analysis System - Development Roadmap

## ✅ Completed: Live Variance Analysis (Nov 21, 2025)

### What Was Done
- **Upgraded `process_uc.py`** to support Plan vs Actuals tracking
- **New Data Structure** with variance calculations at multiple levels:
  - Budget line level: `total_planned`, `total_spent`, `total_variance`
  - Monthly level: `planned`, `claims`, `d365`, `total_spent`, `variance`
  - Cumulative level: running totals across months
  - Grand totals: project-wide summary

### Key Features Implemented
1. **Multi-Column Detection**: Automatically finds Plan, Claims, and D365 columns for each month
2. **Variance Tracking**: Calculates `Variance = Planned - (Claims + D365)` at all levels
3. **Budget Utilization**: Tracks spending efficiency (currently 0% - no actuals yet in data)
4. **Adaptive Column Mapping**: Maps each month to `{'plan': col_idx, 'claims': col_idx, 'd365': col_idx}`

### Output Structure
```json
{
  "monthly_data": {
    "Apr-25": {
      "planned": 0,
      "claims": 0,
      "d365": 0,
      "total_spent": 0,
      "variance": 0
    }
  },
  "cumulative_data": {
    "Apr-25": {
      "cumulative_planned": 0,
      "cumulative_spent": 0,
      "cumulative_variance": 0
    }
  },
  "budget_lines": {
    "Salary - Project Manager": {
      "total_planned": 480000,
      "total_spent": 0,
      "total_variance": 480000,
      "monthly_data": {...},
      "cost_heads": [...]
    }
  },
  "grand_totals": {
    "total_planned": 9908304,
    "total_spent": 0,
    "total_variance": 9908304
  }
}
```

---

## 🔄 Next Steps: Integration & Analysis

### Priority 1: Update Downstream Components
- [ ] **Update `run_risk_analysis.py`** to use new variance data structure
  - Replace `budget_lines[key]['total']` with `budget_lines[key]['total_planned']`
  - Add variance-based risk checks (e.g., overspending alerts)
  - Integrate actual spending patterns into risk scoring

- [ ] **Update `generate_report.py`** to visualize variances
  - Add Plan vs Actuals charts (bar charts, variance graphs)
  - Show monthly spending trends (planned vs actual)
  - Add budget utilization dashboard
  - Highlight overspending/underspending areas

### Priority 2: Cash Flow Analysis (Live)
- [ ] **Implement smart cash redistribution logic**
  - Identify unspent budget by month and budget head
  - Categorize budget heads by flexibility:
    - Fixed: Travel, Statutory expenses (must be spent eventually)
    - Flexible: Office expenses, discretionary items (can be reallocated)
  - Suggest optimal reallocation strategies

- [ ] **Create cash flow forecasting**
  - Project future spending based on historical patterns
  - Flag months with potential cash shortages
  - Recommend timing for billing/tranche releases

### Priority 3: Cost Head Tracking
- [ ] **Cash outflow by cost head**
  - Track spending patterns per cost head across budget lines
  - Identify high-burn cost heads
  - Compare planned vs actual at cost head level

---

## 📊 Reporting & Visualization Improvements

### Static Report Enhancements
- [ ] Rework prompts to better suit variance analysis requirements
- [ ] Add variance-based risk sections:
  - Budget overrun risks
  - Spending velocity analysis
  - Cash runway projections

### Dynamic Dashboard (Future)
- [ ] Generate interactive D3.js dashboard
  - Real-time variance charts
  - Budget utilization gauges
  - Spending trend lines
  - Cost head breakdown
- [ ] Inject into existing website template

---

## 🔍 Risk Analysis Improvements

### Risk Domains (Structured Approach)
Analyze risks by domain to narrow scope and improve accuracy:

#### Financial Risks
- [x] Activity vs Budget mapping (completed with company context)
- [ ] Budget variance risks (overspending/underspending)
- [ ] Cash flow timing risks
- [ ] Billing/tranche delay risks

#### Operational Risks
- [ ] Activity completion delays
- [ ] Resource allocation issues
- [ ] Cost head overruns

#### Strategic Risks
- [ ] Budget reallocation needs
- [ ] Project timeline impacts
- [ ] Milestone funding gaps

---

## 📝 Data Integration Notes

### Activity Plan Alignment
- **Completed**: Activity plans now use cost heads (aligned with UC)
- **Completed**: Automatic activity-to-budget mapping via cost heads
- No more manual mapping needed ✓

### Supporting Documents
- [ ] Summarize context from supporting sheets instead of dumping all text
- [ ] Extract key metrics only (dates, amounts, milestones)
- [ ] Improve context relevance for AI analysis

---

## 🎯 System Capabilities Summary

### Current State (Nov 21, 2025)
- ✅ UC processing with variance tracking
- ✅ Adaptive column detection (plan/claims/d365)
- ✅ Multi-level aggregation (line/monthly/cumulative/grand)
- ✅ Cost head tracking per budget line
- ✅ Company context integration (zero-cost activities)
- ✅ Robust error handling and dynamic output paths

### Still Needed
- ⏳ Variance-based risk analysis
- ⏳ Cash flow forecasting
- ⏳ Smart budget reallocation
- ⏳ Actuals visualization in reports
- ⏳ Interactive dashboards

---

## 🚀 Quick Start for Next Developer

To continue development:

1. **Test with actual spending data**: Add Claims and D365 values to Excel to test variance calculations
2. **Update risk analysis**: Modify `run_risk_analysis.py` to leverage variance data
3. **Enhance reports**: Add variance visualizations to `generate_report.py`
4. **Implement cash flow**: Build redistribution logic based on variance patterns 
