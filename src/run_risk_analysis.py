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
        DATA_DIR, RUNS_DIR, REPORT_DIR,
        ACTIVITY_JSON_PATH, FUNDING_JSON_PATH, UC_JSON_PATH,
        COMPANY_CONTEXT_FILE, RISK_REPORT_PATH,
        LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL,
    )
except ImportError:
    # Fallback paths
    DATA_DIR = PROJECT_ROOT / "Data"
    RUNS_DIR = PROJECT_ROOT / "Runs"
    REPORT_DIR = PROJECT_ROOT / "Report"
    ACTIVITY_JSON_PATH = DATA_DIR / "milestone_activities_processed.json"
    FUNDING_JSON_PATH = DATA_DIR / "funding_tranches_processed.json"
    UC_JSON_PATH = DATA_DIR / "uc_processed.json"
    COMPANY_CONTEXT_FILE = DATA_DIR / "company_context.md"
    RISK_REPORT_PATH = DATA_DIR / "master_risk_report.json"
    LOG_FORMAT = '%(asctime)s - %(levelname)s: %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    LOG_LEVEL = logging.INFO

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
        funding_data: Dictionary from funding_tranches_processed.json
        budget_months: List of month strings in YYYY-MM format
        
    Returns:
        Dictionary mapping each month to cumulative funding
    """
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
    
    try:
        from config.settings import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
    except ImportError:
        OLLAMA_URL = "http://localhost:11434/api/generate"
        OLLAMA_MODEL = "qwen3:4b"
        OLLAMA_TIMEOUT = 300
    
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


def check_strategic_risks(metadata_text, budget_dict):
    """Analyze for strategic risks using AI."""
    import requests
    
    try:
        from config.settings import OLLAMA_URL, OLLAMA_MODEL
    except ImportError:
        OLLAMA_URL = "http://localhost:11434/api/generate"
        OLLAMA_MODEL = "qwen3:4b"
    
    logging.info("Starting strategic risk audit...")
    risks = []
    
    metadata_snippet = metadata_text[:5000] if len(metadata_text) > 5000 else metadata_text
    
    formatted_budget = "\n".join(
        f"- {item}: ₹{amount:,.2f}" for item, amount in list(budget_dict.items())[:15]
    )
    
    prompt = f"""Strategic Risk Auditor: Find contradictions between narrative and budget.

Project Context:
{metadata_snippet[:3000]}

Budget Allocations:
{formatted_budget}

Identify ONLY genuine risks. Return empty list if consistent.
JSON: [{{"risk_type": "...", "severity": "...", "details": "..."}}]
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
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        
        strategic_risks = json.loads(result.get("response", "[]"))
        
        for risk in strategic_risks:
            risks.append({
                "risk_type": risk.get('risk_type', 'Strategic Risk'),
                "severity": risk.get('severity', 'Medium'),
                "details": risk.get('details', 'No details')
            })
        
    except Exception as e:
        logging.error(f"Strategic analysis error: {e}")
    
    logging.info(f"Strategic audit: {len(risks)} risk(s) found")
    return risks


def save_run_outputs(run_dir, uc_data, activity_data, risk_report):
    """Save all outputs to the run directory."""
    
    # Save UC data
    with open(run_dir / "uc_processed.json", "w") as f:
        json.dump(uc_data, f, indent=2)
    
    # Save activity data
    with open(run_dir / "milestone_activities_processed.json", "w") as f:
        json.dump(activity_data, f, indent=2)
    
    # Save risk report
    with open(run_dir / "master_risk_report.json", "w") as f:
        json.dump(risk_report, f, indent=2)
    
    logging.info(f"All outputs saved to: {run_dir}")


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

def main():
    """Main execution entry point."""
    
    # Phase 1: Setup
    logging.info("=" * 80)
    logging.info("PHASE 1: SETUP")
    logging.info("=" * 80)
    
    run_id, run_dir = create_run_directory()
    logging.info(f"Run ID: {run_id}")
    
    # Phase 2: Data Loading
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 2: DATA LOADING")
    logging.info("=" * 80)
    
    try:
        activity_data = load_json_data(ACTIVITY_JSON_PATH)
        funding_data = load_json_data(FUNDING_JSON_PATH)
        uc_data = load_json_data(UC_JSON_PATH)
    except FileNotFoundError as e:
        logging.error(f"Required data file not found: {e}")
        logging.info("Run the processor scripts first (process_uc.py, process_activities.py, process_billing.py)")
        update_run_metadata(run_dir, success=False)
        return 1
    
    # Load company context
    company_context = ""
    if COMPANY_CONTEXT_FILE.exists():
        with open(COMPANY_CONTEXT_FILE, 'r', encoding='utf-8') as f:
            company_context = f.read()
        logging.info(f"Company context loaded: {len(company_context)} chars")
    
    # Load metadata for strategic analysis
    try:
        from src.metadata_extractor import extract_smart_metadata
        from config.settings import METADATA_EXCEL_FILE
        
        if METADATA_EXCEL_FILE.exists():
            raw_metadata_text = extract_smart_metadata(METADATA_EXCEL_FILE)
        else:
            raw_metadata_text = ""
    except Exception as e:
        logging.warning(f"Could not load metadata: {e}")
        raw_metadata_text = ""
    
    # Extract budget months
    budget_months = sorted(uc_data.get('monthly_data', {}).keys())
    logging.info(f"Budget period: {budget_months[0] if budget_months else 'N/A'} to {budget_months[-1] if budget_months else 'N/A'}")
    
    # Calculate cumulative funding
    cumulative_funding = calculate_cumulative_funding(funding_data, budget_months)
    
    # Phase 3: Statistical Analysis
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 3: STATISTICAL ANALYSIS")
    logging.info("=" * 80)
    
    stats_summary = generate_statistics(uc_data, funding_data)
    print(stats_summary)
    
    # Phase 4: Risk Identification
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 4: RISK IDENTIFICATION")
    logging.info("=" * 80)
    
    master_risk_report = []
    
    # 1. Cash Flow Risks
    logging.info("\n[1/4] Cash Flow Risk Analysis")
    cash_flow_risks = check_cash_flow_risk(uc_data, cumulative_funding)
    master_risk_report.extend(cash_flow_risks)
    
    # 2. Contractual Timeline
    logging.info("\n[2/4] Contractual Timeline Check")
    contractual_risks = check_contractual_timelines(funding_data)
    master_risk_report.extend(contractual_risks)
    
    # 3. Activity-Budget Mapping
    logging.info("\n[3/4] Activity-Budget Mapping")
    mapping_risks = check_activity_budget_mapping(activity_data, uc_data, company_context)
    master_risk_report.extend(mapping_risks)
    
    # 4. Strategic Risks
    logging.info("\n[4/4] Strategic Risk Audit")
    budget_dict = {key: line['total_planned'] for key, line in uc_data.get('budget_lines', {}).items()}
    strategic_risks = check_strategic_risks(raw_metadata_text, budget_dict)
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
    
    # Save outputs
    save_run_outputs(run_dir, uc_data, activity_data, master_risk_report)
    
    # Also save to Data/ for backward compatibility
    with open(RISK_REPORT_PATH, 'w') as f:
        json.dump(master_risk_report, f, indent=2)
    
    # Update run metadata
    update_run_metadata(run_dir, success=True)
    
    logging.info("\n" + "=" * 80)
    logging.info(f"ANALYSIS COMPLETE")
    logging.info(f"Run directory: {run_dir}")
    logging.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
