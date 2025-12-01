"""
Risk Engine - Main Analysis Script (Refactored)

This is the main entry point for the risk analysis system.
It orchestrates all processing steps and ensures outputs go to 
timestamped run directories.

USAGE:
    python -m src.run_risk_analysis
    # or from project root:
    python src/run_risk_analysis.py

WORKFLOW:
    1. Setup: Create timestamped run directory
    2. Data Loading: Load and process Excel files
    3. Statistical Analysis: Calculate financial metrics
    4. Risk Identification: Run AI-powered risk checks
    5. Report Generation: Create markdown report with visualizations
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Import configuration
try:
    from config.settings import (
        RUNS_DIR,
        UC_JSON_FILENAME, ACTIVITY_JSON_FILENAME, FUNDING_JSON_FILENAME,
        RISK_REPORT_FILENAME,
        LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL,
        OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT,
    )
except ImportError:
    # Fallback paths
    RUNS_DIR = PROJECT_ROOT / "Runs"
    UC_JSON_FILENAME = "uc_processed.json"
    ACTIVITY_JSON_FILENAME = "milestone_activities_processed.json"
    FUNDING_JSON_FILENAME = "funding_tranches_processed.json"
    RISK_REPORT_FILENAME = "master_risk_report.json"
    LOG_FORMAT = '%(asctime)s - %(levelname)s: %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    LOG_LEVEL = logging.INFO
    OLLAMA_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "gemma3:12b"
    OLLAMA_TIMEOUT = 300

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)


def create_run_directory():
    """
    Create a new timestamped run directory.
    
    Returns:
        Tuple of (run_id, run_dir_path)
    """
    # Generate timestamp-based run ID
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_id = f"run_{timestamp}"
    
    # Create run directory
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Save run metadata
    metadata = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "status": "in_progress",
        "project_root": str(PROJECT_ROOT),
    }
    
    metadata_file = run_dir / "run_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    logging.info(f"Created run directory: {run_dir}")
    
    return run_id, run_dir


def load_json_data(filepath):
    """Load JSON data from a file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        logging.info(f"Loaded: {filepath.name}")
        return data
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {filepath}: {e}")
        raise


def calculate_cumulative_funding(funding_data, budget_months):
    """
    Calculate cumulative funding available for each month.
    
    Args:
        funding_data: Dictionary from funding_tranches_processed.json (can be None)
        budget_months: List of month strings in YYYY-MM format
        
    Returns:
        Dictionary mapping each month to cumulative funding, or None if data is missing
    """
    # Check for missing or empty funding data - enable Fallback Mode
    if not funding_data or not funding_data.get('tranches'):
        logging.warning("⚠️  Funding data missing. Enabling Fallback Mode.")
        return None
    
    from config.settings import normalize_month
    
    logging.info("Calculating cumulative funding by month...")
    
    cumulative_map = {month: 0.0 for month in budget_months}
    
    tranches = funding_data.get('tranches', [])
    logging.info(f"Processing {len(tranches)} funding tranches")
    
    for tranche in tranches:
        billing_value = tranche['billing_value']
        expected_date_str = tranche['expected_billing_date_str']
        
        try:
            # Parse and normalize the date
            if ' ' in expected_date_str:
                date_part = expected_date_str.split(' ')[0]
            else:
                date_part = expected_date_str
            
            billing_date = datetime.strptime(date_part, '%Y-%m-%d')
            
            # Normalize to YYYY-MM format
            month_key = billing_date.strftime('%Y-%m')
            
            if month_key in budget_months:
                month_index = budget_months.index(month_key)
                
                # Add to this month and all subsequent months
                for i in range(month_index, len(budget_months)):
                    cumulative_map[budget_months[i]] += billing_value
                
                logging.debug(f"Added ₹{billing_value:,.0f} from {month_key} onwards")
            else:
                logging.warning(f"Billing month '{month_key}' not found in budget months")
                
        except Exception as e:
            logging.error(f"Error processing tranche: {e}")
            continue
    
    return cumulative_map


def generate_statistics(uc_data, funding_data):
    """Calculate key financial health metrics."""
    logging.info("Generating financial statistics...")
    
    cumulative_spend = uc_data.get('cumulative_data', {})
    budget_months = list(cumulative_spend.keys())
    
    total_planned_spend = 0.0
    if budget_months:
        last_month = budget_months[-1]
        total_planned_spend = cumulative_spend[last_month].get('cumulative_planned', 0)
    
    total_funding = funding_data.get('total_billing_value', 0)
    funding_gap = total_funding - total_planned_spend
    
    # Top 5 costs
    budget_lines = uc_data.get('budget_lines', {})
    budget_line_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
    sorted_costs = sorted(budget_line_totals.items(), key=lambda x: x[1], reverse=True)
    top_5_costs = sorted_costs[:5]
    
    summary = f"\n{'='*60}\n"
    summary += "FINANCIAL STATISTICS\n"
    summary += f"{'='*60}\n"
    summary += f"Total Planned Spend: ₹{total_planned_spend:,.2f}\n"
    summary += f"Total Funding:       ₹{total_funding:,.2f}\n"
    summary += f"Funding Gap/Surplus: ₹{funding_gap:,.2f}"
    
    if funding_gap < 0:
        summary += " ⚠️  DEFICIT\n"
    else:
        summary += " ✓ SURPLUS\n"
    
    summary += f"\nTop 5 Cost Items:\n"
    for i, (item, cost) in enumerate(top_5_costs, 1):
        percentage = (cost / total_planned_spend * 100) if total_planned_spend > 0 else 0
        summary += f"  {i}. {item[:50]:<50} ₹{cost:>12,.2f} ({percentage:>5.1f}%)\n"
    
    summary += f"{'='*60}\n"
    
    return summary


def check_cash_flow_risk(uc_data, cumulative_funding_map):
    """Identify months where spending exceeds available funding."""
    logging.info("Starting cash flow risk analysis...")
    risks = []
    
    cumulative_spending = uc_data.get('cumulative_data', {})
    
    for month, month_data in cumulative_spending.items():
        planned_spend = month_data.get('cumulative_planned', 0.0)
        available_funds = cumulative_funding_map.get(month, 0.0)
        
        if planned_spend > available_funds:
            deficit = planned_spend - available_funds
            risk = {
                "risk_type": "Cash Flow Deficit",
                "severity": "High",
                "month": month,
                "details": f"Planned spending (₹{planned_spend:,.2f}) exceeds funding (₹{available_funds:,.2f}) by ₹{deficit:,.2f}"
            }
            risks.append(risk)
            logging.warning(f"Cash flow deficit in {month}: ₹{deficit:,.2f}")
    
    logging.info(f"Cash flow analysis: {len(risks)} deficit(s) found")
    return risks


def check_contractual_timelines(funding_data):
    """Check if billing dates comply with contractual rules."""
    try:
        from src.compliance_checker import check_contractual_timeline
    except ImportError:
        from compliance_checker import check_contractual_timeline
    
    logging.info("Starting contractual timeline compliance check...")
    risks = []
    
    tranches = funding_data.get('tranches', [])
    
    for tranche in tranches:
        milestone = tranche.get('milestone', 'Unknown')
        planned_date = tranche.get('expected_billing_date_str', 'Unknown')
        contractual_rule = tranche.get('contractual_timeline_str', 'Unknown')
        
        try:
            result = check_contractual_timeline(planned_date, contractual_rule)
            
            if result.get('at_risk', False):
                risk = {
                    "risk_type": "Contractual Timeline Risk",
                    "severity": "Medium",
                    "milestone": milestone,
                    "planned_date": planned_date,
                    "contractual_rule": contractual_rule,
                    "details": result.get('reasoning', 'Potential violation detected')
                }
                risks.append(risk)
                logging.warning(f"Contractual risk: {milestone}")
        except Exception as e:
            logging.error(f"Error checking {milestone}: {e}")
    
    logging.info(f"Contractual timeline check: {len(risks)} violation(s) found")
    return risks


def check_activity_budget_mapping(activity_data, uc_data, company_context=""):
    """Map activities to budget lines and identify gaps."""
    import requests
    
    logging.info("Starting activity-budget mapping analysis...")
    risks = []
    
    # Extract unique activities
    unique_activities = []
    for milestone_name, activities_list in activity_data.items():
        for activity in activities_list:
            activity_name = activity.get('activity', '').strip()
            if activity_name and activity_name not in unique_activities:
                unique_activities.append(activity_name)
    
    # Extract budget lines
    budget_lines = uc_data.get('budget_lines', {})
    budget_line_items = list(budget_lines.keys())
    
    logging.info(f"Analyzing {len(unique_activities)} activities against {len(budget_line_items)} budget lines")
    
    # Process in batches
    BATCH_SIZE = 5
    all_mappings = []
    
    for batch_start in range(0, len(unique_activities), BATCH_SIZE):
        batch_activities = unique_activities[batch_start:batch_start + BATCH_SIZE]
        
        prompt = f"""Map each Activity to the most relevant Budget Line Item.

Company Context:
{company_context[:2000]}

Activities:
{chr(10).join('- ' + act for act in batch_activities)}

Budget Lines:
{chr(10).join('- ' + key for key in budget_line_items[:20])}

Return JSON: [{{"activity": "...", "match": "Budget Line" or null, "reasoning": "..."}}]
"""
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "activity": {"type": "string"},
                    "match": {"type": ["string", "null"]},
                    "reasoning": {"type": "string"}
                },
                "required": ["activity", "match", "reasoning"]
            }
        }
        
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": schema,
                "think": False,
                "keep_alive": "5m",
                "options": {"temperature": 0.0, "num_ctx": 4096}
            }
            
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            
            batch_mappings = json.loads(result.get("response", "[]"))
            all_mappings.extend(batch_mappings)
            
        except Exception as e:
            logging.error(f"Error processing batch: {e}")
    
    # Create risks for unmatched activities
    for mapping in all_mappings:
        if mapping.get('match') is None:
            risks.append({
                "risk_type": "Activity Budget Mapping",
                "severity": "Medium",
                "activity": mapping.get('activity', 'Unknown'),
                "details": f"No budget allocation. {mapping.get('reasoning', '')}"
            })
    
    logging.info(f"Activity mapping: {len(risks)} unfunded activities found")
    return risks


def check_strategic_risks(metadata_text, budget_summary, company_context=""):
    """
    Strategic Risk Auditor: Identify discrepancies between the Narrative goals and Financial reality.
    
    Analyzes for:
    - Unfunded Mandates: Major activities described in text but has 0 budget
    - Timeline Conflicts: Text mentions dates different from budget months
    - Resource Gaps: Text requires specific roles not listed in budget
    
    Args:
        metadata_text: Raw project narrative/metadata from Excel sheets
        budget_summary: Dictionary mapping budget line items to amounts
        company_context: Company-specific rules to ignore certain patterns
        
    Returns:
        List of strategic risk objects (empty list if project is consistent)
    """
    import requests
    
    logging.info("Starting strategic risk audit...")
    risks = []
    
    # Truncate metadata if too long (first 5000 chars for analysis)
    metadata_snippet = metadata_text[:5000] if len(metadata_text) > 5000 else metadata_text
    
    # Format budget with amounts for AI context
    formatted_budget = "\n".join(
        f"- {item}: ₹{amount:,.2f}" for item, amount in list(budget_summary.items())[:25]
    )
    
    # Balanced prompt with good examples and reasonable thresholds
    prompt = f"""You are a Strategic Risk Auditor reviewing a project for meaningful discrepancies between the narrative and budget.

PROJECT NARRATIVE:
{metadata_snippet}

APPROVED BUDGET:
{formatted_budget}

COMPANY CONTEXT (items handled separately - do not flag):
{company_context[:1500] if company_context else "None provided."}

WHAT TO FLAG (Material Risks):
- A major deliverable in the narrative has NO corresponding budget line at all
- The narrative explicitly assigns a task to the implementing organization, but the budget shows the donor/funder is supposed to provide it (or vice versa)
- A core activity (not administrative) is described but completely missing from budget
- Big discrepancies where the narrative states a specific quantity/scale but the budget is too low.

WHAT NOT TO FLAG (Minor/Acceptable):
- Budget line exists but you think the amount "might be a little low" - trust the organization's costing judgment. Don't flag small descrepancies. D
- Administrative activities (approvals, emails, coordination calls) with no budget - these are overhead
- Items where the donor/funder explicitly takes responsibility in the narrative
- Speculative concerns ("what if X happens", "ongoing costs might increase")
- Activities that can reasonably map to an existing budget category

SEVERITY GUIDE:
- HIGH: Core project deliverable completely unbudgeted (e.g., "conduct 50 trainings" but zero training budget)
- MEDIUM: Supporting activity unbudgeted that could impact delivery (e.g., transport for field staff mentioned but no travel budget)
- Ignore minor gaps - only flag issues that would materially impact project success

Return JSON list: [{{"risk_type": "Strategic Risk", "severity": "High/Medium", "details": "The narrative states [X] but the budget [Y]. This creates a risk because [Z]."}}]

If the budget reasonably covers the narrative commitments, return an empty list [].
"""
    
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "risk_type": {"type": "string"},
                "severity": {"type": "string"},
                "details": {"type": "string"}
            },
            "required": ["risk_type", "severity", "details"]
        }
    }
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "keep_alive": "5m",
            "options": {"temperature": 0.0, "num_ctx": 8192}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        strategic_risks = json.loads(result.get("response", "[]"))
        
        # Process and normalize risks
        for risk in strategic_risks:
            risk_obj = {
                "risk_type": "Strategic Risk",  # Always set to Strategic Risk for proper categorization
                "severity": risk.get('severity', 'Medium'),
                "details": risk.get('details', 'No details provided')
            }
            risks.append(risk_obj)
            logging.warning(f"Strategic risk: {risk_obj['details'][:80]}...")
        
        if not risks:
            logging.info("No strategic risks identified - project plan appears consistent.")
        
    except Exception as e:
        logging.error(f"Strategic analysis error: {e}")
    
    logging.info(f"Strategic audit: {len(risks)} risk(s) found")
    return risks


def save_run_outputs(run_dir, risk_report):
    """Save risk report to the run directory."""
    
    # Save risk report
    with open(run_dir / RISK_REPORT_FILENAME, "w") as f:
        json.dump(risk_report, f, indent=2)
    
    logging.info(f"Risk report saved to: {run_dir}")


def update_run_metadata(run_dir, success=True):
    """Update run metadata with completion status."""
    metadata_file = run_dir / "run_metadata.json"
    
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        metadata["status"] = "completed" if success else "failed"
        metadata["completed_at"] = datetime.now().isoformat()
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_analysis(run_dir, company_context="", activity_excel=None):
    """
    Run risk analysis on data in a run directory.
    
    Args:
        run_dir: Path to run directory containing processed JSON files
        company_context: Optional company context text for AI analysis
        activity_excel: Optional path to activity Excel for metadata extraction
        
    Returns:
        0 on success, 1 on failure
    """
    run_dir = Path(run_dir)
    
    # Phase 1: Setup
    logging.info("=" * 80)
    logging.info("RISK ANALYSIS")
    logging.info("=" * 80)
    logging.info(f"Run directory: {run_dir}")
    
    # Phase 2: Data Loading (from run_dir)
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 1: DATA LOADING")
    logging.info("=" * 80)
    
    # Load from run directory
    uc_json_path = run_dir / UC_JSON_FILENAME
    activity_json_path = run_dir / ACTIVITY_JSON_FILENAME
    funding_json_path = run_dir / FUNDING_JSON_FILENAME
    
    try:
        uc_data = load_json_data(uc_json_path)
        activity_data = load_json_data(activity_json_path)
    except FileNotFoundError as e:
        logging.error(f"Required data file not found in run directory: {e}")
        logging.info("Ensure UC and Activity processors have run first")
        update_run_metadata(run_dir, success=False)
        return 1
    
    # Funding data is optional - graceful fallback if missing
    funding_data = None
    if funding_json_path.exists():
        try:
            funding_data = load_json_data(funding_json_path)
        except json.JSONDecodeError:
            logging.warning("⚠️  Funding/billing data file is invalid. Will use Fallback Mode.")
    else:
        logging.warning("⚠️  Funding/billing data file not found. Will use Fallback Mode.")
    
    # Load metadata for strategic analysis AND save to run folder
    raw_metadata_text = ""
    if activity_excel:
        try:
            from src.metadata_extractor import extract_smart_metadata
            raw_metadata_text = extract_smart_metadata(activity_excel)
            
            # Save metadata to run folder for report generation
            if raw_metadata_text:
                metadata_path = run_dir / "project_metadata.txt"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    f.write(raw_metadata_text)
                logging.info(f"Saved project metadata to run folder: {len(raw_metadata_text):,} chars")
                
                # Also save to Data folder for verification
                data_metadata_path = PROJECT_ROOT / "Data" / "project_metadata.txt"
                with open(data_metadata_path, 'w', encoding='utf-8') as f:
                    f.write(raw_metadata_text)
                logging.info(f"Saved project metadata to Data folder for verification")
        except Exception as e:
            logging.warning(f"Could not load metadata: {e}")
    
    # Extract budget months
    budget_months = sorted(uc_data.get('monthly_data', {}).keys())
    logging.info(f"Budget period: {budget_months[0] if budget_months else 'N/A'} to {budget_months[-1] if budget_months else 'N/A'}")
    
    # Calculate cumulative funding (returns None if data missing)
    cumulative_funding = calculate_cumulative_funding(funding_data, budget_months)
    
    # ========================================================================
    # FALLBACK MODE LOGIC
    # ========================================================================
    fallback_mode = cumulative_funding is None
    
    # Calculate total planned spend from UC data
    cumulative_spend = uc_data.get('cumulative_data', {})
    total_planned_spend = 0.0
    if budget_months:
        last_month = budget_months[-1]
        total_planned_spend = cumulative_spend.get(last_month, {}).get('cumulative_planned', 0)
    
    if fallback_mode:
        logging.warning("="*60)
        logging.warning("⚠️  FALLBACK MODE ACTIVATED")
        logging.warning("="*60)
        logging.warning("Billing/Funding data is missing or empty.")
        logging.warning(f"Assuming project is fully funded at ₹{total_planned_spend:,.2f}")
        logging.warning("Financial risk checks will be SKIPPED.")
        logging.warning("="*60)
        
        # Create synthetic funding data for reports
        total_project_funding = total_planned_spend
        cumulative_funding = {month: total_project_funding for month in budget_months}
        
        # Create synthetic funding_data for statistics and report generation
        funding_data = {
            'total_billing_value': total_project_funding,
            'tranches': [],
            '_fallback_mode': True
        }
    
    # Phase 3: Statistical Analysis
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 2: STATISTICAL ANALYSIS")
    logging.info("=" * 80)
    
    stats_summary = generate_statistics(uc_data, funding_data)
    print(stats_summary)
    
    # Phase 4: Risk Identification
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 3: RISK IDENTIFICATION")
    logging.info("=" * 80)
    
    master_risk_report = []
    cash_flow_risks = []
    contractual_risks = []
    
    # 1. Cash Flow Risks (SKIP in Fallback Mode)
    logging.info("\n[1/4] Cash Flow Risk Analysis")
    if fallback_mode:
        logging.info("  ⏭️  SKIPPED - Fallback Mode (no funding data)")
        data_gap_risk = {
            "risk_type": "Data Gap",
            "severity": "High",
            "details": "Billing/Funding data is missing. The system has ASSUMED the project is fully funded to allow operational analysis. Financial risks (cash flow deficits) have been SUPPRESSED. Please provide billing tracker data for accurate financial risk assessment."
        }
        master_risk_report.append(data_gap_risk)
        logging.warning("  ⚠️  Injected 'Data Gap' risk into report")
    else:
        cash_flow_risks = check_cash_flow_risk(uc_data, cumulative_funding)
        master_risk_report.extend(cash_flow_risks)
    
    # 2. Contractual Timeline (SKIP in Fallback Mode)
    logging.info("\n[2/4] Contractual Timeline Check")
    if fallback_mode:
        logging.info("  ⏭️  SKIPPED - Fallback Mode (no funding tranches)")
    else:
        contractual_risks = check_contractual_timelines(funding_data)
        master_risk_report.extend(contractual_risks)
    
    # 3. Activity-Budget Mapping
    logging.info("\n[3/4] Activity-Budget Mapping")
    mapping_risks = check_activity_budget_mapping(activity_data, uc_data, company_context)
    master_risk_report.extend(mapping_risks)
    
    # 4. Strategic Risks (Narrative vs Budget Analysis)
    logging.info("\n[4/4] Strategic Risk Audit (Narrative vs Budget)")
    budget_dict = {key: line['total_planned'] for key, line in uc_data.get('budget_lines', {}).items()}
    strategic_risks = check_strategic_risks(raw_metadata_text, budget_dict, company_context)
    master_risk_report.extend(strategic_risks)
    
    # Summary
    logging.info("\n" + "=" * 80)
    logging.info("RISK SUMMARY")
    logging.info("=" * 80)
    logging.info(f"Total Risks: {len(master_risk_report)}")
    logging.info(f"  - Cash Flow: {len(cash_flow_risks)}")
    logging.info(f"  - Contractual: {len(contractual_risks)}")
    logging.info(f"  - Mapping: {len(mapping_risks)}")
    logging.info(f"  - Strategic: {len(strategic_risks)}")
    
    # Save risk report to run directory
    save_run_outputs(run_dir, master_risk_report)
    
    # Phase 5: Report Generation
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 4: REPORT GENERATION")
    logging.info("=" * 80)
    
    try:
        from src.generate_report import generate_full_report
        
        report_path = generate_full_report(
            run_dir=run_dir,
            uc_data=uc_data,
            funding_data=funding_data,
            risk_report=master_risk_report,
            activity_data=activity_data
        )
        
        logging.info(f"Report saved: {report_path}")
        logging.info("Visualizations saved to run directory:")
        logging.info("  - budget_breakdown.png")
        logging.info("  - monthly_spending_trend.png")
        logging.info("  - category_spending_breakdown.png")
        logging.info("  - risk_severity_distribution.png")
        logging.info("  - risk_type_distribution.png")
        logging.info("  - project_gantt_chart.png")
        
    except Exception as e:
        logging.error(f"Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        logging.info("Continuing without report...")
    
    # Update run metadata
    update_run_metadata(run_dir, success=True)
    
    logging.info("\n" + "=" * 80)
    logging.info(f"ANALYSIS COMPLETE")
    logging.info(f"Run directory: {run_dir}")
    logging.info(f"Outputs:")
    logging.info(f"  - {RISK_REPORT_FILENAME}")
    logging.info(f"  - Project_Risk_Report.md")
    logging.info(f"  - [visualizations]")
    logging.info("=" * 80)
    
    return 0


def main():
    """CLI entry point - for backward compatibility."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run risk analysis on processed data')
    parser.add_argument('run_dir', help='Path to run directory containing processed JSON files')
    parser.add_argument('--context', default="", help='Company context text for AI analysis')
    parser.add_argument('--activity-excel', default=None, help='Path to activity Excel for metadata')
    
    args = parser.parse_args()
    
    return run_analysis(args.run_dir, args.context, args.activity_excel)


if __name__ == "__main__":
    sys.exit(main())
