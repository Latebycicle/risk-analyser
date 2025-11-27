"""
Risk Engine - Main Analysis Script

This script performs comprehensive risk analysis for project funding,
budget utilization, and milestone compliance.

Phase 1: Setup
Phase 2: Data Loading & Pre-processing
Phase 3: Statistical & Visual Analysis
Phase 4: Risk Identification Engine
"""

import json
import logging
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from compliance_checker import check_contractual_timeline, call_ollama_api
from metadata_extractor import extract_smart_metadata

# Configure logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ============================================================================
# FILE PATH CONSTANTS
# ============================================================================

DATA_DIR = Path("Data")
ACTIVITY_JSON_PATH = DATA_DIR / "milestone_activities_processed.json"
FUNDING_JSON_PATH = DATA_DIR / "funding_tranches_processed.json"
UC_JSON_PATH = DATA_DIR / "uc_processed.json"
ACTIVITY_EXCEL_PATH = DATA_DIR / "Ivanti activity sheet_v2.xlsx"

OUTPUT_DIR = DATA_DIR
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json_data(filepath):
    """
    Load JSON data from a file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Dictionary containing the JSON data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        logging.info(f"Successfully loaded: {filepath}")
        return data
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {filepath}: {e}")
        raise


def load_raw_activity_metadata(excel_file):
    """
    Load raw metadata from all Excel sheets except the Activity sheet.
    
    This is used for "Failsafe" analysis to capture contextual information
    that may not be in the structured JSON files.
    
    Args:
        excel_file: Path to the Excel file
        
    Returns:
        String containing concatenated text from all valid sheets
    """
    logging.info(f"Loading raw metadata from: {excel_file}")
    
    try:
        # Open the Excel file
        xl_file = pd.ExcelFile(excel_file)
        
        # List of all sheets
        all_sheets = xl_file.sheet_names
        logging.info(f"Found {len(all_sheets)} sheets in workbook")
        
        raw_metadata_text = ""
        sheets_processed = 0
        
        # Iterate through all sheet names
        for sheet_name in all_sheets:
            # SKIP the "Activity sheet " (note the trailing space)
            if sheet_name == "Activity sheet ":
                logging.info(f"Skipping sheet: '{sheet_name}' (activity data)")
                continue
            
            try:
                # Read the sheet into a dataframe
                df = pd.read_excel(xl_file, sheet_name=sheet_name)
                
                # Convert to string and concatenate
                sheet_text = f"\n\n=== SHEET: {sheet_name} ===\n"
                sheet_text += df.to_string()
                raw_metadata_text += sheet_text
                
                sheets_processed += 1
                logging.debug(f"Processed sheet: {sheet_name}")
                
            except Exception as e:
                logging.warning(f"Could not read sheet '{sheet_name}': {e}")
                continue
        
        logging.info(f"Processed {sheets_processed} sheets into metadata (skipped 1)")
        logging.info(f"Total metadata size: {len(raw_metadata_text)} characters")
        
        return raw_metadata_text
        
    except FileNotFoundError:
        logging.error(f"Excel file not found: {excel_file}")
        raise
    except Exception as e:
        logging.error(f"Error loading raw metadata: {e}")
        raise


def calculate_cumulative_funding(funding_data, budget_months):
    """
    Calculate cumulative funding available for each month.
    
    This creates a timeline showing how much total funding has been
    received by each month (cumulative basis).
    
    Args:
        funding_data: Dictionary from funding_tranches_processed.json
        budget_months: List of month strings (e.g., ["Apr-25", "May-25", ...])
        
    Returns:
        Dictionary mapping each month to cumulative funding received by that date
    """
    logging.info("Calculating cumulative funding by month...")
    
    # Initialize cumulative map with all months set to 0.0
    cumulative_map = {month: 0.0 for month in budget_months}
    
    # Process each funding tranche
    tranches = funding_data.get('tranches', [])
    logging.info(f"Processing {len(tranches)} funding tranches")
    
    for tranche in tranches:
        milestone = tranche['milestone']
        billing_value = tranche['billing_value']
        expected_date_str = tranche['expected_billing_date_str']
        
        # Parse the expected billing date
        try:
            # Handle format like "2025-09-01 00:00:00"
            if ' ' in expected_date_str:
                date_part = expected_date_str.split(' ')[0]
            else:
                date_part = expected_date_str
            
            billing_date = datetime.strptime(date_part, '%Y-%m-%d')
            
            # Format to match budget keys: "Sep-25" or "Nov 25"
            # Try both formats since UC data has inconsistent formatting
            month_key_dash = billing_date.strftime('%b-%y')
            month_key_space = billing_date.strftime('%b %y')
            
            # Determine which format matches the budget months
            month_key = None
            if month_key_dash in budget_months:
                month_key = month_key_dash
            elif month_key_space in budget_months:
                month_key = month_key_space
            
            logging.info(
                f"Tranche: {milestone[:50]}... | "
                f"Amount: ₹{billing_value:,.0f} | "
                f"Expected: {month_key if month_key else month_key_dash}"
            )
            
            # Find the index of this month in budget_months
            if month_key and month_key in budget_months:
                month_index = budget_months.index(month_key)
                
                # Add billing value to this month and all subsequent months
                for i in range(month_index, len(budget_months)):
                    cumulative_map[budget_months[i]] += billing_value
                
                logging.debug(f"Added ₹{billing_value:,.0f} from {month_key} onwards")
            else:
                logging.warning(
                    f"Billing month '{month_key}' not found in budget months. "
                    f"Tranche: {milestone[:30]}..."
                )
                
        except Exception as e:
            logging.error(
                f"Error processing tranche '{milestone[:30]}...': {e}"
            )
            continue
    
    # Log summary
    total_funding = funding_data.get('total_billing_value', 0)
    final_cumulative = cumulative_map[budget_months[-1]] if budget_months else 0
    
    logging.info(f"Total project funding: ₹{total_funding:,.2f}")
    logging.info(f"Final cumulative (last month): ₹{final_cumulative:,.2f}")
    
    return cumulative_map


def generate_statistics(uc_data, funding_data):
    """
    Calculate key financial health metrics.
    
    Args:
        uc_data: Dictionary from uc_processed.json
        funding_data: Dictionary from funding_tranches_processed.json
        
    Returns:
        Formatted string summary of financial statistics
    """
    logging.info("Generating financial statistics...")
    
    # Get total planned spend (last value from cumulative) - updated for variance structure
    cumulative_spend = uc_data['cumulative_data']
    budget_months = list(cumulative_spend.keys())
    total_planned_spend = cumulative_spend[budget_months[-1]]['cumulative_planned'] if budget_months else 0
    
    # Get total funding
    total_funding = funding_data['total_billing_value']
    
    # Calculate funding gap/surplus
    funding_gap = total_funding - total_planned_spend
    
    # Get top 5 costs - updated to use total_planned
    budget_lines = uc_data['budget_lines']
    budget_line_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
    sorted_costs = sorted(
        budget_line_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )
    top_5_costs = sorted_costs[:5]
    
    # Build summary string
    summary = "\n" + "=" * 60 + "\n"
    summary += "FINANCIAL STATISTICS\n"
    summary += "=" * 60 + "\n"
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
    
    summary += "=" * 60 + "\n"
    
    return summary


def plot_cash_flow(uc_data, cumulative_funding_map, budget_months, output_file='cash_flow_graph.png'):
    """
    Generate a line graph comparing Cumulative Spend vs. Cumulative Funding.
    
    Args:
        uc_data: Dictionary from uc_processed.json
        cumulative_funding_map: Dictionary mapping months to cumulative funding
        budget_months: List of month strings in order
        output_file: Path to save the output graph (default: 'cash_flow_graph.png')
    """
    logging.info("Generating cash flow visualization...")
    
    # Extract cumulative spend values for each month - updated for variance structure
    cumulative_spend_values = [
        uc_data['cumulative_data'][month]['cumulative_planned']
        for month in budget_months
    ]
    
    # Extract cumulative funding values for each month
    cumulative_funding_values = [
        cumulative_funding_map[month]
        for month in budget_months
    ]
    
    # Create the plot
    plt.figure(figsize=(14, 8))
    
    # Use step plot for both lines to show discrete monthly changes
    # Spending: step plot showing spending accumulates at end of each month
    plt.step(
        budget_months,
        cumulative_spend_values,
        where='post',
        marker='o',
        linewidth=2,
        label='Cumulative Planned Spending',
        color='#e74c3c'
    )
    
    # Funding: step plot showing funding arrives in chunks
    plt.step(
        budget_months,
        cumulative_funding_values,
        where='post',
        marker='s',
        linewidth=2,
        label='Cumulative Funding Received',
        color='#27ae60'
    )
    
    # Add title and labels
    plt.title('Project Cash Flow Analysis', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Month', fontsize=12, fontweight='bold')
    plt.ylabel('Amount (₹)', fontsize=12, fontweight='bold')
    
    # Add grid
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Add legend
    plt.legend(loc='upper left', fontsize=11, framealpha=0.9)
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    
    # Format y-axis to show currency
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1e6:.1f}M'))
    
    # Tight layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logging.info(f"Cash flow graph saved to: {output_file}")
    
    # Close the plot to free memory
    plt.close()


# ============================================================================
# PHASE 4: RISK IDENTIFICATION ENGINE
# ============================================================================

def check_cash_flow_risk(uc_data, cumulative_funding_map):
    """
    Deterministic Check: Identify months where cumulative planned spend exceeds available funding.
    
    Args:
        uc_data: Processed UC data containing cumulative_planned_spending
        cumulative_funding_map: Dict mapping months to cumulative funding amounts
        
    Returns:
        List of risk objects for cash flow deficits
    """
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
                "details": f"Planned spending (₹{planned_spend:,.2f}) exceeds available funding (₹{available_funds:,.2f}) by ₹{deficit:,.2f}"
            }
            risks.append(risk)
            logging.warning(f"Cash flow deficit detected in {month}: ₹{deficit:,.2f}")
    
    logging.info(f"Cash flow analysis complete. Found {len(risks)} deficit(s).")
    return risks


def check_contractual_timelines(funding_data):
    """
    AI-Powered Check: Verify if planned billing dates comply with contractual requirements.
    
    Args:
        funding_data: Processed funding data containing tranches
        
    Returns:
        List of risk objects for contractual timeline violations
    """
    logging.info("Starting contractual timeline compliance check...")
    risks = []
    
    tranches = funding_data.get('tranches', [])
    
    for tranche in tranches:
        milestone = tranche.get('milestone', 'Unknown')
        planned_date = tranche.get('expected_billing_date_str', 'Unknown')
        contractual_rule = tranche.get('contractual_timeline_str', 'Unknown')
        
        logging.info(f"Checking contractual compliance for: {milestone} (Date: {planned_date}, Rule: {contractual_rule})")
        
        result = check_contractual_timeline(planned_date, contractual_rule)
        
        if result.get('at_risk', False):
            risk = {
                "risk_type": "Contractual Timeline Risk",
                "severity": "Medium",
                "milestone": milestone,
                "planned_date": planned_date,
                "contractual_rule": contractual_rule,
                "details": result.get('reasoning', 'Potential contractual timeline violation detected')
            }
            risks.append(risk)
            logging.warning(f"Contractual risk detected for {milestone}: {result.get('reasoning')}")
    
    logging.info(f"Contractual timeline check complete. Found {len(risks)} violation(s).")
    return risks


def check_strategic_risks(metadata_text, budget_dict):
    """
    Strategic Risk Auditor: Find contradictions between narrative and financial reality.
    
    Args:
        metadata_text: Raw extracted metadata from project documents
        budget_dict: Dictionary mapping budget line items to their allocated amounts
        
    Returns:
        List of strategic risk objects (empty list if no genuine risks found)
    """
    logging.info("Starting strategic risk audit...")
    risks = []
    
    # Truncate metadata if too long (use first 5000 chars for analysis)
    metadata_snippet = metadata_text[:5000] if len(metadata_text) > 5000 else metadata_text
    
    # Format budget with amounts for better AI context
    formatted_budget_list = "\n".join(
        f"- {item}: ₹{amount:,.2f}" for item, amount in budget_dict.items()
    )
    
    prompt = f"""You are a Strategic Risk Auditor.
Project Context (Narrative):
{metadata_snippet}

Approved Budget Allocations:
{formatted_budget_list}

Task: Analyze for discrepancies between the Narrative goals and Financial reality.
- Is a major activity described in the text but has ₹0 or low budget?
- Is the timeline in the text different from the funding reality?
- Are there compliance rules (audits, reports) in the text that are unfunded?

Output: A JSON list of risk objects.
IMPORTANT: Identify **only genuine** contradictions. Do not invent risks to fill a quota. If the project plan appears consistent, return an empty list [].
"""
    
    # Define structured output schema
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
        # Use structured output with direct API call
        import requests
        payload = {
            "model": "qwen3:4b",
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0.0,
                "num_ctx": 8192
            }
        }
        
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        response_text = result.get("response", "")
        
        # Parse JSON array
        strategic_risks = json.loads(response_text)
        
        # Only add risks if we actually got some
        if strategic_risks and len(strategic_risks) > 0:
            for risk in strategic_risks:
                risk_obj = {
                    "risk_type": risk.get('risk_type', 'Strategic Risk'),
                    "severity": risk.get('severity', 'Medium'),
                    "details": risk.get('details', 'No details provided')
                }
                risks.append(risk_obj)
                logging.warning(f"Strategic risk: {risk_obj['details'][:100]}...")
        else:
            logging.info("No strategic risks identified - project plan appears consistent.")
        
        logging.info(f"Strategic risk audit complete. Found {len(risks)} risk(s).")
    
    except Exception as e:
        logging.error(f"Error in strategic risk analysis: {e}")
        risks.append({
            "risk_type": "Strategic Risk",
            "severity": "Low",
            "details": f"Strategic analysis failed: {str(e)}"
        })
    
    return risks


def check_activity_budget_mapping(activity_data, uc_data, company_context=""):
    """
    AI-Powered Check: Map activities to budget lines and identify unfunded activities.
    Uses batched processing with semantic matching instead of "find missing" logic.
    
    Args:
        activity_data: Processed activity data containing milestones and activities
        uc_data: Processed UC data containing budget line items
        company_context: Company-specific rules for zero-cost activities and mappings
        
    Returns:
        List of risk objects for activities without budget
    """
    logging.info("Starting activity-budget mapping analysis...")
    risks = []
    
    # Extract unique activity names
    unique_activities = []
    for milestone_name, activities_list in activity_data.items():
        for activity in activities_list:
            activity_name = activity.get('activity', '').strip()
            if activity_name and activity_name not in unique_activities:
                unique_activities.append(activity_name)
    
    # Extract budget line items with cost heads information
    budget_lines = uc_data.get('budget_lines', {})
    budget_line_items = list(budget_lines.keys())
    
    # Also extract cost heads for semantic matching
    all_cost_heads = []
    for line_item, line_data in budget_lines.items():
        cost_heads = line_data.get('cost_heads', [])
        all_cost_heads.extend(cost_heads)
    
    logging.info(f"Analyzing {len(unique_activities)} activities against {len(budget_line_items)} budget lines (with {len(all_cost_heads)} cost heads)...")
    
    # Process activities in batches of 5 for better accuracy
    BATCH_SIZE = 5
    all_mappings = []
    
    for batch_start in range(0, len(unique_activities), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(unique_activities))
        batch_activities = unique_activities[batch_start:batch_end]
        
        logging.info(f"Processing batch {batch_start//BATCH_SIZE + 1}/{(len(unique_activities)-1)//BATCH_SIZE + 1} ({len(batch_activities)} activities)...")
        
        # Construct matching prompt with company context and budget lines
        prompt = f"""You are a budget analyst. Map each Project Activity to the most relevant Budget Line Item.

Company Operational Context (Rules for exclusions):
{company_context}

Activities to Map:
{chr(10).join('- ' + act for act in batch_activities)}

Available Budget Lines (with Cost Heads):
{chr(10).join('- ' + key + ' (Cost Heads: ' + ', '.join(budget_lines[key]['cost_heads']) + ')' for key in budget_line_items)}

Task:
1. **Check the "Company Context" first.** If the activity is listed as "Zero-Cost" (e.g., approvals, emails, signing), set "match": "Administrative (No Budget Required)".
2. **Otherwise, attempt to map to a Budget Line:**
   - "Conduct assessment" matches "Training Aids - Assessment".
   - "Hire HR" matches "Salary - Project Manager" or similar.
   - "Training of Trainees" matches "Training of Trainees - Trainer 1" or "Training of Trainees - Trainer 2".
   - If NO logical match exists, set "match": null.

Return JSON list:
[
  {{"activity": "...", "match": "Budget Line Name" or "Administrative (No Budget Required)" (or null), "reasoning": "..."}}
]
"""
        
        # Define structured output schema for batch
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
            # Call Ollama with qwen3:4b model (gpt-oss:20b returns empty responses)
            payload = {
                "model": "qwen3:4b",
                "prompt": prompt,
                "stream": False,
                "format": schema,
                "think": False,
                "keep_alive": "5m",
                "options": {
                    "temperature": 0.0,
                    "num_ctx": 4096
                }
            }
            
            import requests
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=300)
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "")
            
            # Debug: Log the raw response
            logging.debug(f"Raw response from model: {response_text[:200]}...")
            
            # Check if response is empty
            if not response_text or response_text.strip() == "":
                raise ValueError("Model returned empty response")
            
            # Parse JSON response
            batch_mappings = json.loads(response_text)
            
            # Validate that we got a list
            if not isinstance(batch_mappings, list):
                raise ValueError(f"Expected list, got {type(batch_mappings)}")
            
            all_mappings.extend(batch_mappings)
            logging.info(f"Batch {batch_start//BATCH_SIZE + 1} processed successfully: {len(batch_mappings)} mappings")
            
        except Exception as e:
            logging.error(f"Error processing batch {batch_start//BATCH_SIZE + 1}: {e}")
            # Add all activities in failed batch as risks with error note
            for activity_name in batch_activities:
                risks.append({
                    "risk_type": "Activity Budget Mapping",
                    "severity": "Low",
                    "activity": activity_name,
                    "details": f"Could not analyze due to error: {str(e)}"
                })
    
    # Process all mappings and create risks only for null matches
    for mapping in all_mappings:
        activity_name = mapping.get('activity', '')
        match = mapping.get('match')
        reasoning = mapping.get('reasoning', 'No reasoning provided')
        
        if match is None or match == "null":
            # No match found - create a risk
            risk = {
                "risk_type": "Activity Budget Mapping",
                "severity": "Medium",
                "activity": activity_name,
                "details": f"No budget allocation found. Analysis: {reasoning}"
            }
            risks.append(risk)
            logging.warning(f"Unfunded activity detected: {activity_name}")
        elif match == "Administrative (No Budget Required)":
            # Zero-cost administrative activity - log but don't flag as risk
            logging.info(f"Activity '{activity_name}' identified as administrative (zero-cost): {reasoning}")
        else:
            # Match found - log but don't create risk
            logging.debug(f"Activity '{activity_name}' mapped to '{match}': {reasoning}")
    
    logging.info(f"Activity-budget mapping complete. Found {len(risks)} unfunded activity/activities.")
    return risks





# ============================================================================
# MAIN EXECUTION BLOCK
# ============================================================================

if __name__ == "__main__":
    # Phase 1: Setup
    logging.info("=" * 80)
    logging.info("PHASE 1: SETUP")
    logging.info("=" * 80)
    
    # Phase 2: Data Loading & Pre-processing
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 2: DATA LOADING & PRE-PROCESSING")
    logging.info("=" * 80)
    
    activity_data = load_json_data(ACTIVITY_JSON_PATH)
    funding_data = load_json_data(FUNDING_JSON_PATH)
    uc_data = load_json_data(UC_JSON_PATH)
    
    # Load smart-filtered metadata for strategic analysis
    logging.info("\nExtracting strategic metadata from Excel...")
    raw_metadata_text = extract_smart_metadata(ACTIVITY_EXCEL_PATH)
    logging.info(f"Metadata extracted: {len(raw_metadata_text):,} characters")
    
    # Load company context for zero-cost activity identification
    company_context_file = DATA_DIR / "company_context.md"
    company_context = ""
    if company_context_file.exists():
        with open(company_context_file, 'r', encoding='utf-8') as f:
            company_context = f.read()
        logging.info(f"Company context loaded: {len(company_context)} characters")
    else:
        logging.warning(f"Company context file not found: {company_context_file}")
    
    # Save metadata for record
    metadata_file = OUTPUT_DIR / "project_metadata.txt"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        f.write(raw_metadata_text)
    logging.info(f"Metadata saved to: {metadata_file}")
    
    # Extract budget months from UC data (updated for new variance analysis structure)
    budget_months = list(uc_data['monthly_data'].keys())
    logging.info(f"Budget period: {budget_months[0]} to {budget_months[-1]} ({len(budget_months)} months)")
    
    cumulative_funding = calculate_cumulative_funding(funding_data, budget_months)
    
    # Phase 3: Statistical & Visual Analysis
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 3: STATISTICAL & VISUAL ANALYSIS")
    logging.info("=" * 80)
    
    stats_summary = generate_statistics(uc_data, funding_data)
    print(stats_summary)
    
    plot_cash_flow(uc_data, cumulative_funding, budget_months)
    logging.info(f"Cash flow graph saved to: {OUTPUT_DIR / 'cash_flow_graph.png'}")
    
    # Phase 4: Risk Identification Engine
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 4: RISK IDENTIFICATION ENGINE")
    logging.info("=" * 80)
    
    # Initialize master risk report
    master_risk_report = []
    
    # 1. Check Cash Flow Risks (Deterministic)
    logging.info("\n[1/3] Cash Flow Risk Analysis")
    cash_flow_risks = check_cash_flow_risk(uc_data, cumulative_funding)
    master_risk_report.extend(cash_flow_risks)
    
    # 2. Check Contractual Timeline Compliance (AI-Powered)
    logging.info("\n[2/3] Contractual Timeline Compliance Check")
    contractual_risks = check_contractual_timelines(funding_data)
    master_risk_report.extend(contractual_risks)
    
    # 3. Check Activity-Budget Mapping (AI-Powered)
    logging.info("\n[3/4] Activity-Budget Mapping Analysis")
    mapping_risks = check_activity_budget_mapping(activity_data, uc_data, company_context)
    master_risk_report.extend(mapping_risks)
    
    # 4. Check Strategic Risks (AI-Failsafe with Metadata) - updated for variance structure
    logging.info("\n[4/4] Strategic Risk Audit (Narrative vs Budget)")
    budget_dict = {key: line['total_planned'] for key, line in uc_data['budget_lines'].items()}
    strategic_risks = check_strategic_risks(raw_metadata_text, budget_dict)
    master_risk_report.extend(strategic_risks)
    
    # Summary
    logging.info("\n" + "=" * 80)
    logging.info("PHASE 4 COMPLETE - RISK SUMMARY")
    logging.info("=" * 80)
    logging.info(f"Total Risks Identified: {len(master_risk_report)}")
    logging.info(f"  - Cash Flow Deficits: {len(cash_flow_risks)}")
    logging.info(f"  - Contractual Timeline Risks: {len(contractual_risks)}")
    logging.info(f"  - Activity-Budget Mapping Issues: {len(mapping_risks)}")
    logging.info(f"  - Strategic Risks: {len(strategic_risks)}")
    
    # Save risk report to JSON
    risk_report_path = OUTPUT_DIR / "master_risk_report.json"
    with open(risk_report_path, 'w') as f:
        json.dump(master_risk_report, f, indent=2)
    logging.info(f"\nMaster Risk Report saved to: {risk_report_path}")
    
    logging.info("\n" + "=" * 80)
    logging.info("RISK ANALYSIS COMPLETE")
    logging.info("=" * 80)
