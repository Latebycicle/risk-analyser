"""
Report Generator - Stakeholder-Focused Risk & Financial Intelligence

This module generates comprehensive Markdown reports with focus on:
1. Operational Runways & Cash Flow Analysis
2. Risk visibility (before graphs)
3. Clean, actionable visualizations

Output: run_dir/Project_Risk_Report.md (ready for PDF export)

USAGE:
    from src.generate_report import generate_full_report
    generate_full_report(run_dir="/path/to/run_folder")
"""

import json
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import numpy as np

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Import configuration
try:
    from config.settings import RUNS_DIR, OLLAMA_MODEL
except ImportError:
    RUNS_DIR = PROJECT_ROOT / "Runs"
    OLLAMA_MODEL = "gemma3:12b"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# ============================================================================
# DATA LOADING
# ============================================================================

def load_analysis_data(run_dir):
    """Load all analysis data from JSON files in run directory."""
    logging.info("Loading analysis data...")
    
    if run_dir is None:
        raise ValueError("run_dir is required")
    
    run_dir = Path(run_dir)
    
    with open(run_dir / "uc_processed.json", 'r') as f:
        uc_data = json.load(f)
    
    # Funding data is optional
    funding_data = None
    funding_path = run_dir / "funding_tranches_processed.json"
    if funding_path.exists():
        with open(funding_path, 'r') as f:
            funding_data = json.load(f)
            # Check for empty/fallback funding data
            if not funding_data.get('tranches'):
                logging.warning("Funding data has no tranches - will use fallback mode")
    
    # Risk report is optional
    risk_report = []
    risk_path = run_dir / "master_risk_report.json"
    if risk_path.exists():
        with open(risk_path, 'r') as f:
            risk_report = json.load(f)
    
    with open(run_dir / "milestone_activities_processed.json", 'r') as f:
        milestone_data = json.load(f)
    
    logging.info(f"Loaded: {len(risk_report)} risks identified")
    return uc_data, funding_data, risk_report, milestone_data


def parse_project_metadata(run_dir):
    """Parse project_metadata.txt to extract key overview details."""
    logging.info("Parsing project metadata...")
    
    metadata = {}
    
    if run_dir:
        metadata_path = Path(run_dir) / "project_metadata.txt"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                lines = content.split('\n')
                in_overview_section = False
                
                for line in lines:
                    line_stripped = line.strip()
                    
                    if 'SHEET: Project Overview' in line:
                        in_overview_section = True
                        continue
                    
                    if in_overview_section and 'SHEET:' in line and 'Project Overview' not in line:
                        break
                    
                    if in_overview_section and '|' in line:
                        parts = [p.strip() for p in line.split('|')]
                        parts = [p for p in parts if p]
                        
                        if len(parts) >= 2:
                            key = parts[0]
                            value = parts[1]
                            
                            if not key or not value:
                                continue
                            
                            skip_keys = ['Field', 'Project overview', '---', 'Unnamed:', ':--']
                            skip_values = ['Details', 'Unnamed: 1', 'Unnamed:', '---', ':--']
                            
                            if any(sk in key for sk in skip_keys) or any(sv in value for sv in skip_values):
                                continue
                            
                            if key.startswith(':') or key.startswith('-'):
                                continue
                            
                            key_lower = key.lower()
                            
                            if 'project title' in key_lower:
                                metadata['Project Title'] = value
                            elif 'brief project description' in key_lower:
                                metadata['Brief Project Description'] = value
                            elif 'project funder' in key_lower:
                                metadata['Project Funder'] = value
                            elif 'project entity' in key_lower:
                                metadata['Project Entity'] = value
                            elif 'mou effective start date' in key_lower:
                                if '00:00:00' in value:
                                    value = value.replace(' 00:00:00', '')
                                metadata['MOU Effective Start Date'] = value
                            elif 'mou end date' in key_lower:
                                if '00:00:00' in value:
                                    value = value.replace(' 00:00:00', '')
                                metadata['MOU End Date'] = value
                            elif 'deployment region' in key_lower or 'region' in key_lower:
                                metadata['Deployment Region'] = value
                
            except Exception as e:
                logging.warning(f"Error parsing metadata: {e}")
    
    return {
        "Title": metadata.get("Project Title", "Project Risk Analysis"),
        "Description": metadata.get("Brief Project Description", "Automated risk analysis report"),
        "Funder": metadata.get("Project Funder", "N/A"),
        "Entity": metadata.get("Project Entity", "N/A"),
        "Start Date": metadata.get("MOU Effective Start Date", "N/A"),
        "End Date": metadata.get("MOU End Date", "N/A"),
        "Region": metadata.get("Deployment Region", "N/A"),
    }


# ============================================================================
# STATISTICS & CALCULATIONS
# ============================================================================

def calculate_dashboard_stats(uc_data, funding_data, risk_report):
    """Calculate key dashboard statistics."""
    logging.info("Calculating dashboard statistics...")
    
    # Handle missing funding data
    if funding_data is None or not funding_data.get('tranches'):
        total_value = 0.0
        for month_data in uc_data.get('cumulative_data', {}).values():
            if month_data.get('cumulative_planned', 0) > total_value:
                total_value = month_data.get('cumulative_planned', 0)
        logging.info(f"  Using total planned spend as project value: ₹{total_value:,.0f}")
    else:
        total_value = funding_data.get('total_billing_value', 0)
    
    # Project Duration
    monthly_data = uc_data.get('monthly_data', {})
    active_months = [m for m, d in monthly_data.items() if d.get('planned', 0) > 0]
    duration = len(active_months)
    
    # Average Monthly Burn
    avg_monthly_burn = total_value / duration if duration > 0 else 0
    
    # Highest Cost Item
    budget_lines = uc_data.get('budget_lines', {})
    if budget_lines:
        budget_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
        highest_item = max(budget_totals.items(), key=lambda x: x[1])
        highest_cost_name = highest_item[0]
        highest_cost_value = highest_item[1]
    else:
        highest_cost_name = "N/A"
        highest_cost_value = 0.0
    
    # Risk counts
    high_risks = sum(1 for r in risk_report if str(r.get('severity', '')).lower() == 'high')
    medium_risks = sum(1 for r in risk_report if str(r.get('severity', '')).lower() == 'medium')
    
    return {
        'total_value': total_value,
        'duration': duration,
        'avg_monthly_burn': avg_monthly_burn,
        'highest_cost_name': highest_cost_name,
        'highest_cost_value': highest_cost_value,
        'high_risks': high_risks,
        'medium_risks': medium_risks,
        'total_risks': len(risk_report)
    }


def calculate_cash_position(uc_data, funding_data):
    """
    Calculate Net Cash Position = Cumulative Funding - Cumulative Planned Spend.
    
    Returns:
        List of dicts with month, cumulative_funding, cumulative_spend, net_position
    """
    logging.info("Calculating cash position...")
    
    all_months = sorted(uc_data.get('monthly_data', {}).keys())
    active_months = [m for m in all_months if uc_data['monthly_data'].get(m, {}).get('planned', 0) > 0]
    
    # Build cumulative funding map
    cumulative_funding_map = {month: 0.0 for month in all_months}
    
    tranches = funding_data.get('tranches', []) if funding_data else []
    has_funding_data = bool(tranches)
    
    if has_funding_data:
        for tranche in tranches:
            try:
                tranche_date_str = tranche.get('expected_billing_date_str', '')
                if not tranche_date_str:
                    continue
                
                date_part = tranche_date_str.split()[0] if ' ' in tranche_date_str else tranche_date_str
                tranche_date = datetime.strptime(date_part, '%Y-%m-%d')
                tranche_month = tranche_date.strftime('%Y-%m')
                billing_value = tranche.get('billing_value', 0)
                
                found_month = False
                for month in all_months:
                    if month == tranche_month:
                        found_month = True
                    if found_month:
                        cumulative_funding_map[month] += billing_value
                        
            except Exception as e:
                logging.warning(f"Could not process tranche: {e}")
    
    # Build position data
    position_data = []
    for month in active_months:
        cumulative_spend = uc_data.get('cumulative_data', {}).get(month, {}).get('cumulative_planned', 0)
        cumulative_funding = cumulative_funding_map.get(month, 0)
        net_position = cumulative_funding - cumulative_spend
        
        position_data.append({
            'month': month,
            'cumulative_funding': cumulative_funding,
            'cumulative_spend': cumulative_spend,
            'net_position': net_position,
            'monthly_spend': uc_data.get('monthly_data', {}).get(month, {}).get('planned', 0)
        })
    
    return position_data, has_funding_data


def format_month_label(month_str):
    """Convert YYYY-MM to Mon-YY format (e.g., Apr-25)."""
    try:
        dt = datetime.strptime(month_str, '%Y-%m')
        return dt.strftime('%b-%y')
    except:
        return month_str


# ============================================================================
# VISUALIZATIONS - NEW CHARTS
# ============================================================================

def generate_bank_balance_cliff_chart(uc_data, funding_data, output_folder):
    """
    Generate "The Bank Balance Cliff" - Stepped Line Chart showing Net Cash Position.
    
    Features:
    - Green fill where Balance > 0
    - Red fill where Balance < 0
    - Horizontal line at Y=0 centered vertically (break-even line)
    - Symmetric Y-axis for better readability
    """
    logging.info("  Generating Bank Balance Cliff chart...")
    
    output_folder = Path(output_folder)
    position_data, has_funding_data = calculate_cash_position(uc_data, funding_data)
    
    if not has_funding_data or not position_data:
        logging.warning("    Skipping - no funding data available")
        return False
    
    # Prepare data
    months = [format_month_label(d['month']) for d in position_data]
    net_positions = [d['net_position'] for d in position_data]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # X positions
    x = np.arange(len(months))
    
    # Plot stepped line
    ax.step(x, net_positions, where='mid', linewidth=2.5, color='#2c3e50', label='Net Cash Position')
    
    # Fill areas
    positive_mask = np.array(net_positions) >= 0
    negative_mask = np.array(net_positions) < 0
    
    # Green fill for positive
    y_positive = np.where(positive_mask, net_positions, 0)
    ax.fill_between(x, 0, y_positive, step='mid', alpha=0.4, color='#27ae60', label='Surplus')
    
    # Red fill for negative
    y_negative = np.where(negative_mask, net_positions, 0)
    ax.fill_between(x, 0, y_negative, step='mid', alpha=0.4, color='#e74c3c', label='Deficit')
    
    # Draw the "crash line" at Y=0
    ax.axhline(y=0, color='#c0392b', linestyle='--', linewidth=2.5, label='Break-even Line')
    
    # ============ CENTER Y=0 IN THE MIDDLE OF THE CHART ============
    # Calculate symmetric Y-axis limits so 0 is centered
    max_abs_value = max(abs(min(net_positions)), abs(max(net_positions)))
    # Add 20% padding for annotations and visual breathing room
    y_limit = max_abs_value * 1.2
    ax.set_ylim(-y_limit, y_limit)
    
    # Add colored background bands for visual clarity
    ax.axhspan(0, y_limit, alpha=0.05, color='#27ae60')  # Light green for surplus zone
    ax.axhspan(-y_limit, 0, alpha=0.05, color='#e74c3c')  # Light red for deficit zone
    
    # Add zone labels on the right side
    ax.text(len(months) - 0.5, y_limit * 0.7, 'SURPLUS\nZONE', 
            fontsize=10, fontweight='bold', color='#27ae60', alpha=0.7,
            ha='center', va='center')
    ax.text(len(months) - 0.5, -y_limit * 0.7, 'DEFICIT\nZONE', 
            fontsize=10, fontweight='bold', color='#c0392b', alpha=0.7,
            ha='center', va='center')
    
    # Styling
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Net Cash Position (₹)', fontsize=12, fontweight='bold')
    ax.set_title('The Bank Balance Cliff\nNet Cash Position Over Time', 
                 fontsize=16, fontweight='bold', pad=20)
    
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha='right', fontsize=10)
    
    # Format y-axis with better labels
    def format_currency(val, p):
        if val == 0:
            return '₹0'
        elif abs(val) >= 100000:
            return f'₹{val/100000:+.1f}L'
        else:
            return f'₹{val/1000:+.0f}K'
    
    ax.yaxis.set_major_formatter(plt.FuncFormatter(format_currency))
    
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', fontsize=10)
    
    # Add annotations for critical points
    min_position = min(net_positions)
    max_position = max(net_positions)
    
    # Annotate lowest point
    min_idx = net_positions.index(min_position)
    if min_position < 0:
        ax.annotate(f'Max Deficit\n₹{abs(min_position)/100000:.1f}L',
                   xy=(min_idx, min_position),
                   xytext=(min_idx + 0.5, min_position - y_limit * 0.15),
                   fontsize=9, fontweight='bold', color='#c0392b',
                   arrowprops=dict(arrowstyle='->', color='#c0392b'))
    else:
        # Annotate the lowest surplus point (closest to break-even)
        ax.annotate(f'Min Buffer\n₹{min_position/1000:.0f}K',
                   xy=(min_idx, min_position),
                   xytext=(min_idx + 0.5, min_position - y_limit * 0.15),
                   fontsize=9, fontweight='bold', color='#f39c12',
                   arrowprops=dict(arrowstyle='->', color='#f39c12'))
    
    # Annotate highest point
    max_idx = net_positions.index(max_position)
    ax.annotate(f'Peak\n₹{max_position/100000:.1f}L' if max_position >= 100000 else f'Peak\n₹{max_position/1000:.0f}K',
               xy=(max_idx, max_position),
               xytext=(max_idx + 0.5, max_position + y_limit * 0.1),
               fontsize=9, fontweight='bold', color='#27ae60',
               arrowprops=dict(arrowstyle='->', color='#27ae60'))
    
    plt.tight_layout()
    
    output_path = output_folder / "bank_balance_cliff.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logging.info(f"    Saved: {output_path.name}")
    return True


def generate_budget_heatmap(uc_data, output_folder):
    """
    Generate Budget Heatmap - Top 10 Budget Heads (rows) vs Months (columns).
    
    Darker color = Higher spend.
    """
    logging.info("  Generating Budget Heatmap...")
    
    output_folder = Path(output_folder)
    
    budget_lines = uc_data.get('budget_lines', {})
    monthly_data = uc_data.get('monthly_data', {})
    
    # Get active months
    active_months = sorted([m for m, d in monthly_data.items() if d.get('planned', 0) > 0])
    
    if not active_months or not budget_lines:
        logging.warning("    Skipping - insufficient data")
        return False
    
    # Get top 10 budget heads by total
    budget_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
    sorted_items = sorted(budget_totals.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_items[:10]
    top_10_names = [item[0] for item in top_10]
    
    # Build heatmap data
    heatmap_data = []
    for budget_head in top_10_names:
        row = []
        line_monthly = budget_lines[budget_head].get('monthly_data', {})
        for month in active_months:
            value = line_monthly.get(month, {}).get('planned', 0)
            row.append(value)
        heatmap_data.append(row)
    
    heatmap_array = np.array(heatmap_data)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Create heatmap
    cmap = plt.cm.YlOrRd  # Yellow-Orange-Red colormap
    im = ax.imshow(heatmap_array, aspect='auto', cmap=cmap)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Monthly Spend (₹)', fontsize=11)
    
    # Set ticks and labels
    month_labels = [format_month_label(m) for m in active_months]
    ax.set_xticks(np.arange(len(active_months)))
    ax.set_xticklabels(month_labels, rotation=45, ha='right', fontsize=10)
    
    # Truncate long budget head names
    short_names = [name[:40] + '...' if len(name) > 40 else name for name in top_10_names]
    ax.set_yticks(np.arange(len(top_10_names)))
    ax.set_yticklabels(short_names, fontsize=9)
    
    # Add value annotations
    for i in range(len(top_10_names)):
        for j in range(len(active_months)):
            value = heatmap_array[i, j]
            if value > 0:
                text_color = 'white' if value > heatmap_array.max() * 0.5 else 'black'
                text = f'{value/1000:.0f}K' if value >= 1000 else f'{value:.0f}'
                ax.text(j, i, text, ha='center', va='center', fontsize=8, color=text_color)
    
    ax.set_title('Budget Heatmap\nMonthly Spending by Top 10 Cost Heads', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Budget Head', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    output_path = output_folder / "budget_heatmap.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logging.info(f"    Saved: {output_path.name}")
    return True


def generate_stacked_monthly_burn_chart(uc_data, output_folder):
    """
    Generate Stacked Monthly Burn chart.
    
    Vertical bar chart with monthly spend broken down by Top 5 Cost Heads + Others.
    """
    logging.info("  Generating Stacked Monthly Burn chart...")
    
    output_folder = Path(output_folder)
    
    budget_lines = uc_data.get('budget_lines', {})
    monthly_data = uc_data.get('monthly_data', {})
    
    # Get active months
    active_months = sorted([m for m, d in monthly_data.items() if d.get('planned', 0) > 0])
    
    if not active_months or not budget_lines:
        logging.warning("    Skipping - insufficient data")
        return False
    
    # Get top 5 budget heads
    budget_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
    sorted_items = sorted(budget_totals.items(), key=lambda x: x[1], reverse=True)
    top_5 = [item[0] for item in sorted_items[:5]]
    other_heads = [item[0] for item in sorted_items[5:]]
    
    # Build stacked data
    stack_data = {head: [] for head in top_5}
    stack_data['Others'] = []
    
    for month in active_months:
        # Top 5 values
        for head in top_5:
            value = budget_lines[head].get('monthly_data', {}).get(month, {}).get('planned', 0)
            stack_data[head].append(value)
        
        # Others total
        others_total = 0
        for head in other_heads:
            others_total += budget_lines[head].get('monthly_data', {}).get(month, {}).get('planned', 0)
        stack_data['Others'].append(others_total)
    
    # Create figure with extra bottom margin for legend
    fig, ax = plt.subplots(figsize=(14, 9))
    
    month_labels = [format_month_label(m) for m in active_months]
    x = np.arange(len(active_months))
    width = 0.7
    
    # Colors for stacks
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#95a5a6']
    
    # Stack bars
    bottom = np.zeros(len(active_months))
    all_keys = top_5 + ['Others']
    
    for i, key in enumerate(all_keys):
        values = np.array(stack_data[key])
        short_label = key[:45] + '...' if len(key) > 45 else key
        ax.bar(x, values, width, bottom=bottom, label=short_label, color=colors[i % len(colors)])
        bottom += values
    
    # Styling
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Monthly Spend (₹)', fontsize=12, fontweight='bold')
    ax.set_title('Stacked Monthly Burn\nSpending Breakdown by Category', 
                 fontsize=16, fontweight='bold', pad=20)
    
    ax.set_xticks(x)
    ax.set_xticklabels(month_labels, rotation=45, ha='right', fontsize=10)
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, p: f'₹{val/100000:.1f}L' if val >= 100000 else f'₹{val/1000:.0f}K'))
    
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Legend below chart - 2 columns for full text visibility
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=10,
              frameon=True, fancybox=True, shadow=True)
    
    # Adjust layout to make room for legend below
    plt.subplots_adjust(bottom=0.30)
    
    output_path = output_folder / "stacked_monthly_burn.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logging.info(f"    Saved: {output_path.name}")
    return True


def generate_budget_flow_chart(uc_data, output_folder):
    """
    Generate Budget Flow Hierarchy - Bipartite graph showing Budget Head → Vendor/Role mapping.
    
    Visual Design:
    - Left Column: Budget Heads (categories)
    - Right Column: Vendor/Role items with cost bars
    - Lines connecting Budget Heads to their items
    """
    logging.info("  Generating Budget Flow Hierarchy chart...")
    
    output_folder = Path(output_folder)
    budget_lines = uc_data.get('budget_lines', {})
    
    if not budget_lines:
        logging.warning("    Skipping - no budget data")
        return False
    
    # Group items by budget_head
    budget_head_groups = defaultdict(list)
    for item_key, item_data in budget_lines.items():
        budget_head = item_data.get('budget_head', 'Uncategorized')
        if not budget_head or budget_head == '':
            budget_head = 'Uncategorized'
        budget_head_groups[budget_head].append({
            'name': item_key,
            'vendor_role': item_data.get('vendor_role_category', item_key),
            'total_planned': item_data.get('total_planned', 0),
            'total_spent': item_data.get('total_spent', 0)
        })
    
    # Sort budget heads by total value
    budget_head_totals = {
        head: sum(item['total_planned'] for item in items)
        for head, items in budget_head_groups.items()
    }
    sorted_heads = sorted(budget_head_totals.keys(), key=lambda h: budget_head_totals[h], reverse=True)
    
    # Limit to top 8 budget heads for readability
    sorted_heads = sorted_heads[:8]
    
    # Calculate positions
    total_items = sum(len(budget_head_groups[h]) for h in sorted_heads)
    
    # Create figure
    fig_height = max(10, total_items * 0.5 + 2)
    fig, ax = plt.subplots(figsize=(16, fig_height))
    
    # X positions
    x_budget_head = 0.0
    x_vendor_role = 0.5
    x_bar_start = 0.6
    x_bar_end = 0.95
    
    # Colors for budget heads
    head_colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
                   '#1abc9c', '#e67e22', '#34495e']
    
    # Calculate Y positions
    y_positions_heads = {}
    y_positions_items = {}
    
    current_y = 0
    max_planned = max((item['total_planned'] for items in budget_head_groups.values() for item in items), default=1)
    
    for head_idx, head in enumerate(sorted_heads):
        items = budget_head_groups[head]
        # Sort items by value
        items = sorted(items, key=lambda x: x['total_planned'], reverse=True)
        
        head_start_y = current_y
        
        for item in items:
            y_positions_items[item['name']] = current_y
            current_y += 1
        
        # Budget head Y is centered among its items
        head_end_y = current_y - 1
        y_positions_heads[head] = (head_start_y + head_end_y) / 2
        
        current_y += 0.5  # Gap between groups
    
    # Normalize Y to 0-1 range
    max_y = current_y
    for key in y_positions_heads:
        y_positions_heads[key] = 1 - (y_positions_heads[key] / max_y)
    for key in y_positions_items:
        y_positions_items[key] = 1 - (y_positions_items[key] / max_y)
    
    # Draw Budget Heads (left column)
    for head_idx, head in enumerate(sorted_heads):
        y = y_positions_heads[head]
        color = head_colors[head_idx % len(head_colors)]
        
        # Draw budget head box - full text, larger font
        head_short = head[:35] + '...' if len(head) > 35 else head
        ax.text(x_budget_head, y, head_short, fontsize=11, fontweight='bold',
                ha='right', va='center', color=color,
                bbox=dict(boxstyle='round,pad=0.4', facecolor=color, alpha=0.2, edgecolor=color))
    
    # Draw items and connections
    for head_idx, head in enumerate(sorted_heads):
        items = sorted(budget_head_groups[head], key=lambda x: x['total_planned'], reverse=True)
        color = head_colors[head_idx % len(head_colors)]
        head_y = y_positions_heads[head]
        
        for item in items:
            item_y = y_positions_items[item['name']]
            
            # Draw connection line
            ax.plot([x_budget_head + 0.02, x_vendor_role - 0.02], [head_y, item_y],
                   color=color, alpha=0.4, linewidth=1.5, linestyle='-')
            
            # Draw item name - larger font, more chars
            item_short = item['vendor_role'][:25] + '...' if len(item['vendor_role']) > 25 else item['vendor_role']
            ax.text(x_vendor_role, item_y, item_short, fontsize=10,
                   ha='left', va='center', color='#2c3e50')
            
            # Draw budget bars
            bar_width = (item['total_planned'] / max_planned) * (x_bar_end - x_bar_start)
            spent_width = (item['total_spent'] / max_planned) * (x_bar_end - x_bar_start) if item['total_spent'] > 0 else 0
            
            bar_height = 0.018
            
            # Background bar (total planned) - grey
            ax.add_patch(plt.Rectangle((x_bar_start, item_y - bar_height/2), 
                                        bar_width, bar_height,
                                        facecolor='#bdc3c7', edgecolor='#95a5a6', linewidth=0.5))
            
            # Foreground bar (spent) - green
            if spent_width > 0:
                ax.add_patch(plt.Rectangle((x_bar_start, item_y - bar_height/2), 
                                            spent_width, bar_height,
                                            facecolor='#27ae60', edgecolor='#1e8449', linewidth=0.5))
            
            # Value label - larger font
            value_text = f'₹{item["total_planned"]/1000:.0f}K' if item['total_planned'] < 100000 else f'₹{item["total_planned"]/100000:.1f}L'
            ax.text(x_bar_start + bar_width + 0.01, item_y, value_text,
                   fontsize=9, ha='left', va='center', color='#555555', fontweight='bold')
    
    # Styling
    ax.set_xlim(-0.15, 1.1)
    ax.set_ylim(-0.05, 1.05)
    ax.axis('off')
    
    # Title
    ax.set_title('Budget Flow Hierarchy\nCategory → Item → Allocation', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Column headers - larger fonts
    ax.text(x_budget_head, 1.03, 'Budget Category', fontsize=13, fontweight='bold',
           ha='right', va='bottom', color='#2c3e50')
    ax.text(x_vendor_role, 1.03, 'Cost Item', fontsize=13, fontweight='bold',
           ha='left', va='bottom', color='#2c3e50')
    ax.text((x_bar_start + x_bar_end) / 2, 1.03, 'Allocation', fontsize=13, fontweight='bold',
           ha='center', va='bottom', color='#2c3e50')
    
    # Legend - larger bars and fonts
    legend_y = -0.02
    ax.add_patch(plt.Rectangle((x_bar_start, legend_y - 0.01), 0.06, 0.016,
                                facecolor='#bdc3c7', edgecolor='#95a5a6'))
    ax.text(x_bar_start + 0.07, legend_y, 'Planned', fontsize=10, va='center', color='#555555', fontweight='bold')
    
    ax.add_patch(plt.Rectangle((x_bar_start + 0.18, legend_y - 0.01), 0.06, 0.016,
                                facecolor='#27ae60', edgecolor='#1e8449'))
    ax.text(x_bar_start + 0.25, legend_y, 'Spent', fontsize=10, va='center', color='#555555', fontweight='bold')
    
    plt.tight_layout()
    
    output_path = output_folder / "budget_flow.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logging.info(f"    Saved: {output_path.name}")
    return True


def generate_improved_gantt_chart(milestone_data, output_folder):
    """
    Generate improved Gantt chart.
    
    Features:
    - Color by Quarter (Q1, Q2, Q3, Q4)
    - Minimum bar duration of 15 days for visibility
    - Month gridlines
    """
    logging.info("  Generating improved Gantt chart...")
    
    output_folder = Path(output_folder)
    
    # Collect all activities
    activities = []
    for category, tasks in milestone_data.items():
        for task in tasks:
            try:
                start = datetime.fromisoformat(task['start_date_iso'])
                end = datetime.fromisoformat(task['end_date_iso'])
                duration = (end - start).days
                
                # Enforce minimum duration of 15 days for visibility
                if duration < 15:
                    end = start + timedelta(days=15)
                    duration = 15
                
                activities.append({
                    'category': category,
                    'activity': task['activity'],
                    'start': start,
                    'end': end,
                    'duration': duration
                })
            except Exception as e:
                logging.warning(f"    Could not parse task dates: {e}")
    
    if not activities:
        logging.warning("    No activities to create Gantt chart")
        return False
    
    # Sort by start date
    activities = sorted(activities, key=lambda x: x['start'])
    
    # Determine quarters for coloring
    def get_quarter(date):
        month = date.month
        if month <= 3:
            return 'Q4'  # Jan-Mar (fiscal Q4)
        elif month <= 6:
            return 'Q1'  # Apr-Jun (fiscal Q1)
        elif month <= 9:
            return 'Q2'  # Jul-Sep (fiscal Q2)
        else:
            return 'Q3'  # Oct-Dec (fiscal Q3)
    
    quarter_colors = {
        'Q1': '#3498db',  # Blue - Apr-Jun
        'Q2': '#2ecc71',  # Green - Jul-Sep
        'Q3': '#f39c12',  # Orange - Oct-Dec
        'Q4': '#9b59b6',  # Purple - Jan-Mar
    }
    
    # Create figure
    fig, ax = plt.subplots(figsize=(18, max(10, len(activities) * 0.4)))
    
    # Plot each activity
    y_positions = range(len(activities))
    bar_height = 0.6
    
    for i, task in enumerate(activities):
        start_date = task['start']
        duration = task['duration']
        quarter = get_quarter(start_date)
        color = quarter_colors.get(quarter, '#95a5a6')
        
        ax.barh(i, duration, left=mdates.date2num(start_date), height=bar_height,
                color=color, edgecolor='white', linewidth=0.5, alpha=0.85)
    
    # Y-axis labels (truncated activity names)
    labels = [task['activity'][:60] + ('...' if len(task['activity']) > 60 else '') 
              for task in activities]
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=9)
    
    # X-axis formatting
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
    plt.xticks(rotation=45, ha='right', fontsize=10)
    
    # Grid lines for months
    ax.grid(axis='x', linestyle='--', alpha=0.5)
    ax.grid(axis='y', linestyle=':', alpha=0.3)
    
    # Title and labels
    ax.set_title('Project Timeline\nActivities by Quarter', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    
    # Legend for quarters
    legend_patches = [Patch(facecolor=color, label=f'{quarter} (Fiscal)', edgecolor='white')
                      for quarter, color in quarter_colors.items()]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=10)
    
    # Invert y-axis so earliest tasks are at top
    ax.invert_yaxis()
    
    plt.tight_layout()
    
    output_path = output_folder / "project_gantt_chart.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logging.info(f"    Saved: {output_path.name}")
    return True


# ============================================================================
# MARKDOWN REPORT GENERATION
# ============================================================================

def generate_markdown_report(uc_data, funding_data, risk_report, stats, project_overview, 
                             output_folder, file_inventory=None, charts_generated=None):
    """
    Generate comprehensive Markdown report in new stakeholder-focused format.
    
    Order:
    1. Title & Project Context
    2. Executive Dashboard
    3. ⚠️ Detailed Risk Analysis (MOVED UP - before graphs)
    4. 💰 Financial Intelligence
    5. 📅 Project Timeline
    6. Appendix (Tables)
    """
    logging.info("Generating Markdown report...")
    
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    report_path = output_folder / "Project_Risk_Report.md"
    charts_generated = charts_generated or {}
    
    # Calculate cash position data
    position_data, has_funding_data = calculate_cash_position(uc_data, funding_data)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        # ================================================================
        # 1. TITLE & PROJECT CONTEXT
        # ================================================================
        f.write(f"# {project_overview.get('Title', 'Project Risk Analysis')}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n")
        
        description = project_overview.get('Description', 'N/A')
        if description and description != 'N/A':
            f.write(f"> {description}\n\n")
        
        f.write("| **Field** | **Details** |\n")
        f.write("|-----------|-------------|\n")
        f.write(f"| 🏢 **Funder** | {project_overview.get('Funder', 'N/A')} |\n")
        f.write(f"| 🏛️ **Implementing Entity** | {project_overview.get('Entity', 'N/A')} |\n")
        f.write(f"| 📍 **Region** | {project_overview.get('Region', 'N/A')} |\n")
        f.write(f"| 📆 **Project Period** | {project_overview.get('Start Date', 'N/A')} to {project_overview.get('End Date', 'N/A')} |\n\n")
        
        f.write("---\n\n")
        
        # ================================================================
        # 2. EXECUTIVE DASHBOARD
        # ================================================================
        f.write("## Executive Dashboard\n\n")
        
        f.write("### Key Metrics at a Glance\n\n")
        f.write("| **Metric** | **Value** |\n")
        f.write("|------------|----------|\n")
        f.write(f"| 💰 Total Project Value | **₹{stats['total_value']:,.0f}** |\n")
        f.write(f"| 📅 Active Duration | {stats['duration']} months |\n")
        f.write(f"| 🔥 Avg Monthly Burn | ₹{stats['avg_monthly_burn']:,.0f} |\n")
        f.write(f"| 📈 Highest Cost Item | {stats['highest_cost_name'][:40]}{'...' if len(stats['highest_cost_name']) > 40 else ''} |\n")
        f.write(f"| ⚠️ **Total Risks** | **{stats['total_risks']}** ({stats['high_risks']} High, {stats['medium_risks']} Medium) |\n\n")
        
        # Quick health indicator
        if stats['high_risks'] > 0:
            f.write("🔴 **Health Status:** Immediate attention required\n\n")
        elif stats['medium_risks'] > 2:
            f.write("🟡 **Health Status:** Monitor closely\n\n")
        else:
            f.write("🟢 **Health Status:** On track\n\n")
        
        f.write("---\n\n")
        
        # ================================================================
        # 3. RISK ANALYSIS - Split into Strategic and Operational
        # ================================================================
        
        # Separate strategic risks from operational risks
        strategic_risks = [r for r in risk_report if r.get('risk_type') == 'Strategic Risk']
        operational_risks = [r for r in risk_report if r.get('risk_type') != 'Strategic Risk']
        
        f.write("## Risk Analysis\n\n")
        
        if not risk_report:
            f.write("*No risks identified in this analysis.*\n\n")
        else:
            # ============ STRATEGIC RISKS (Narrative vs Budget) ============
            f.write("### Strategic Risk Analysis\n\n")
            f.write("*Discrepancies between project narrative and financial allocations.*\n\n")
            
            if strategic_risks:
                for risk in strategic_risks:
                    severity = risk.get('severity', 'Medium')
                    details = risk.get('details', 'No details provided')
                    
                    # Severity indicator
                    if severity.lower() == 'high':
                        severity_indicator = "🔴 HIGH"
                    elif severity.lower() == 'medium':
                        severity_indicator = "🟡 MEDIUM"
                    else:
                        severity_indicator = "🔵 LOW"
                    
                    # Strategic risks in distinctive blockquote format
                    f.write(f"> **{severity_indicator}**\n>\n")
                    f.write(f"> {details}\n\n")
            else:
                f.write("✅ **No strategic discrepancies detected.** The project narrative appears consistent with the approved budget.\n\n")
            
            # ============ OPERATIONAL RISKS (by type) ============
            # Group operational risks by type
            risks_by_type = defaultdict(list)
            for risk in operational_risks:
                risk_type = risk.get('risk_type', 'Other')
                risks_by_type[risk_type].append(risk)
            
            # Sort by count (most common first)
            sorted_types = sorted(risks_by_type.items(), key=lambda x: len(x[1]), reverse=True)
            
            for risk_type, risks in sorted_types:
                f.write(f"### {risk_type} ({len(risks)})\n\n")
                
                for risk in risks:
                    severity = risk.get('severity', 'Unknown')
                    
                    # Severity indicator (color-coded)
                    if severity.lower() == 'high':
                        severity_indicator = "🔴 HIGH"
                    elif severity.lower() == 'medium':
                        severity_indicator = "🟡 MEDIUM"
                    else:
                        severity_indicator = "🔵 LOW"
                    
                    # Get activity/milestone name - use risk_type context for budgetary risks
                    item_name = risk.get('activity') or risk.get('milestone') or risk.get('month')
                    
                    # Risk details/description
                    details_main = risk.get('details', 'No details provided')
                    
                    # Clean blockquote format for readability
                    f.write(f"> **{severity_indicator}**\n>\n")
                    if item_name:
                        f.write(f"> **Activity:** {item_name}\n>\n")
                    f.write(f"> {details_main}\n\n")
                
                f.write("\n")
        
        f.write("---\n\n")
        
        # ================================================================
        # 4. 💰 FINANCIAL INTELLIGENCE
        # ================================================================
        f.write("## Financial Intelligence\n\n")
        
        # A. Bank Balance Cliff
        if charts_generated.get('bank_balance_cliff'):
            f.write("### The Bank Balance Cliff\n\n")
            f.write("Shows net cash position over time. **Red zones indicate cash deficit periods.**\n\n")
            f.write("![Bank Balance Cliff](bank_balance_cliff.png)\n\n")
        elif not has_funding_data:
            f.write("### Cash Position\n\n")
            f.write("> ⚠️ **Funding data not available.** Cash flow analysis could not be generated.\n")
            f.write("> Please provide billing tracker data for complete financial insights.\n\n")
        
        # ==================== FINANCIAL LEDGER TABLE ====================
        f.write("### Financial Ledger\n\n")
        f.write("Complete monthly breakdown of funds in, planned vs actual spending, and running balance.\n\n")
        
        # Build comprehensive ledger data
        ledger_rows = []
        running_balance = 0.0
        cumulative_funds_in = 0.0
        cumulative_planned = 0.0
        cumulative_actual = 0.0
        
        # Build funding by month map
        funding_by_month = defaultdict(float)
        tranches = funding_data.get('tranches', []) if funding_data else []
        for tranche in tranches:
            try:
                tranche_date_str = tranche.get('expected_billing_date_str', '')
                if tranche_date_str:
                    date_part = tranche_date_str.split()[0] if ' ' in tranche_date_str else tranche_date_str
                    tranche_date = datetime.strptime(date_part, '%Y-%m-%d')
                    tranche_month = tranche_date.strftime('%Y-%m')
                    funding_by_month[tranche_month] += tranche.get('billing_value', 0)
            except Exception:
                pass
        
        # Get active months from UC data
        monthly_data = uc_data.get('monthly_data', {})
        active_months = sorted([m for m, d in monthly_data.items() if d.get('planned', 0) > 0 or d.get('total_spent', 0) > 0])
        
        for month in active_months:
            month_data = monthly_data.get(month, {})
            
            # Get values
            funds_in = funding_by_month.get(month, 0.0)
            planned = month_data.get('planned', 0.0)
            actual = month_data.get('total_spent', 0.0)  # From claims + d365
            
            # Use actual if available, otherwise use planned for projections
            spend_for_balance = actual if actual > 0 else planned
            
            # Variance: Planned - Actual (positive = under-spend/savings, negative = over-spend)
            variance = planned - actual
            
            # Update cumulatives
            cumulative_funds_in += funds_in
            cumulative_planned += planned
            cumulative_actual += actual
            
            # Calculate running balance: Funds In - Spend (use actual if available, else planned)
            cumulative_spend_for_balance = cumulative_actual if cumulative_actual > 0 else cumulative_planned
            running_balance = cumulative_funds_in - cumulative_spend_for_balance
            
            ledger_rows.append({
                'month': month,
                'funds_in': funds_in,
                'planned': planned,
                'actual': actual,
                'variance': variance,
                'running_balance': running_balance,
                'cumulative_funds_in': cumulative_funds_in,
                'cumulative_planned': cumulative_planned,
                'cumulative_actual': cumulative_actual
            })
        
        # Write ledger table
        f.write("| **Month** | **Funds In** | **Planned** | **Actual** | **Variance** | **Balance** |\n")
        f.write("|:---------:|-------------:|------------:|-----------:|-------------:|------------:|\n")
        
        for row in ledger_rows:
            month_label = format_month_label(row['month'])
            funds_in = row['funds_in']
            planned = row['planned']
            actual = row['actual']
            variance = row['variance']
            balance = row['running_balance']
            
            # Format funds_in (show ✅ if received)
            funds_in_str = f"✅ ₹{funds_in:,.0f}" if funds_in > 0 else "—"
            
            # Format variance (positive = good, negative = overspend)
            if variance > 0:
                variance_str = f"📉 ₹{variance:,.0f}"  # Under-spend
            elif variance < 0:
                variance_str = f"**🔺 ₹{abs(variance):,.0f}**"  # Over-spend (bold)
            else:
                variance_str = "—"
            
            # Format balance (red if negative)
            if balance < 0:
                balance_str = f"🔴 **-₹{abs(balance):,.0f}**"
            elif balance < planned * 0.5:  # Warning if less than half month's budget
                balance_str = f"🟡 ₹{balance:,.0f}"
            else:
                balance_str = f"🟢 ₹{balance:,.0f}"
            
            f.write(f"| {month_label} | {funds_in_str} | ₹{planned:,.0f} | ₹{actual:,.0f} | {variance_str} | {balance_str} |\n")
        
        # Totals row
        total_funds_in = sum(row['funds_in'] for row in ledger_rows)
        total_planned = sum(row['planned'] for row in ledger_rows)
        total_actual = sum(row['actual'] for row in ledger_rows)
        total_variance = total_planned - total_actual
        
        # Final balance uses actual if available, otherwise planned
        total_spend_for_balance = total_actual if total_actual > 0 else total_planned
        final_balance = total_funds_in - total_spend_for_balance
        
        f.write("|-----------|-------------:|------------:|-----------:|-------------:|------------:|\n")
        
        # Variance formatting for totals
        if total_variance >= 0:
            total_var_str = f"📉 ₹{total_variance:,.0f}"
        else:
            total_var_str = f"**🔺 ₹{abs(total_variance):,.0f}**"
        
        # Final balance formatting
        if final_balance < 0:
            final_bal_str = f"🔴 **-₹{abs(final_balance):,.0f}**"
        else:
            final_bal_str = f"🟢 ₹{final_balance:,.0f}"
        
        f.write(f"| **TOTAL** | **₹{total_funds_in:,.0f}** | **₹{total_planned:,.0f}** | **₹{total_actual:,.0f}** | {total_var_str} | {final_bal_str} |\n\n")
        
        # Add legend
        f.write("**Legend:** 📉 Under-spend (savings) | 🔺 Over-spend (risk) | 🟢 Healthy | 🟡 Low | 🔴 Deficit\n\n")
        
        # B. Budget Heatmap
        if charts_generated.get('budget_heatmap'):
            f.write("### Budget Heatmap\n\n")
            f.write("Darker colors indicate **higher spending**. Quickly identify when major costs occur.\n\n")
            f.write("![Budget Heatmap](budget_heatmap.png)\n\n")
        
        # C. Stacked Monthly Burn
        if charts_generated.get('stacked_monthly_burn'):
            f.write("### Monthly Burn by Category\n\n")
            f.write("Monthly spending broken down by top cost categories.\n\n")
            f.write("![Stacked Monthly Burn](stacked_monthly_burn.png)\n\n")
        
        # D. Budget Flow Hierarchy
        if charts_generated.get('budget_flow'):
            f.write("### Budget Flow Hierarchy\n\n")
            f.write("Visual mapping of **Budget Categories** to **Cost Items** with allocation bars.\n\n")
            f.write("![Budget Flow Hierarchy](budget_flow.png)\n\n")
        
        # Top 10 Allocations Table (replaces bar chart)
        f.write("### Top 10 Budget Allocations\n\n")
        
        budget_lines = uc_data.get('budget_lines', {})
        budget_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
        sorted_items = sorted(budget_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        total_budget = sum(budget_totals.values())
        
        f.write("| **#** | **Item** | **Cost** | **% of Total** |\n")
        f.write("|------:|----------|----------:|---------------:|\n")
        
        for i, (item, cost) in enumerate(sorted_items, 1):
            pct = (cost / total_budget * 100) if total_budget > 0 else 0
            item_short = item[:50] + '...' if len(item) > 50 else item
            f.write(f"| {i} | {item_short} | ₹{cost:,.0f} | {pct:.1f}% |\n")
        
        f.write("\n---\n\n")
        
        # ================================================================
        # 5. 📅 PROJECT TIMELINE
        # ================================================================
        f.write("## Project Timeline\n\n")
        
        if charts_generated.get('gantt_chart'):
            f.write("Tasks colored by **fiscal quarter**. Minimum bar width ensures visibility.\n\n")
            f.write("![Project Gantt Chart](project_gantt_chart.png)\n\n")
        else:
            f.write("*Timeline visualization could not be generated.*\n\n")
        
        f.write("---\n\n")
        
        # ================================================================
        # 6. APPENDIX
        # ================================================================
        f.write("## Appendix\n\n")
        
        # Data Sources
        f.write("### Data Sources Analyzed\n\n")
        
        if file_inventory:
            f.write("| **File Type** | **Filename** | **Status** |\n")
            f.write("|---------------|--------------|------------|\n")
            
            uc_file = Path(file_inventory.get('uc', '')).name if file_inventory.get('uc') else 'N/A'
            uc_status = '✓ Found' if file_inventory.get('uc') else '✗ Missing'
            f.write(f"| UC/Budget | `{uc_file}` | {uc_status} |\n")
            
            activity_file = Path(file_inventory.get('activity', '')).name if file_inventory.get('activity') else 'N/A'
            activity_status = '✓ Found' if file_inventory.get('activity') else '✗ Missing'
            f.write(f"| Activity/Plan | `{activity_file}` | {activity_status} |\n")
            
            billing_file = Path(file_inventory.get('billing', '')).name if file_inventory.get('billing') else 'N/A'
            billing_status = '✓ Found' if file_inventory.get('billing') else '✗ Missing'
            f.write(f"| Billing/Tracker | `{billing_file}` | {billing_status} |\n\n")
        
        # Report Metadata
        f.write("### Report Metadata\n\n")
        f.write(f"- **Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
        f.write(f"- **Analysis Engine:** Risk Analyzer v3.0\n")
        f.write(f"- **AI Model:** Ollama {OLLAMA_MODEL} (local)\n\n")
        
        f.write("---\n\n")
        f.write("*End of Report*\n")
    
    logging.info(f"Report saved: {report_path}")
    return report_path


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def generate_full_report(run_dir=None, uc_data=None, funding_data=None, risk_report=None,
                         activity_data=None, file_inventory=None):
    """
    Generate complete report with all visualizations.
    
    Args:
        run_dir: Path to run directory for output
        uc_data: Pre-loaded UC data (optional)
        funding_data: Pre-loaded funding data (optional)
        risk_report: Pre-loaded risk report (optional)
        activity_data: Pre-loaded activity/milestone data (optional)
        file_inventory: Dictionary with identified file paths
        
    Returns:
        Path to generated report
    """
    logging.info("=" * 60)
    logging.info("REPORT GENERATOR v3.0 - Starting")
    logging.info("=" * 60)
    
    if run_dir is None:
        raise ValueError("run_dir is required")
    
    output_path = Path(run_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load data if not provided
    if uc_data is None or funding_data is None or risk_report is None or activity_data is None:
        logging.info("Loading data from run directory...")
        uc_data_loaded, funding_data_loaded, risk_report_loaded, milestone_data_loaded = load_analysis_data(run_dir)
        
        if uc_data is None:
            uc_data = uc_data_loaded
        if funding_data is None:
            funding_data = funding_data_loaded
        if risk_report is None:
            risk_report = risk_report_loaded
        if activity_data is None:
            activity_data = milestone_data_loaded
    
    # Parse project metadata
    project_overview = parse_project_metadata(run_dir)
    
    # Load file inventory if not provided
    if file_inventory is None:
        file_inventory_path = output_path / 'file_inventory.json'
        if file_inventory_path.exists():
            try:
                with open(file_inventory_path, 'r') as f:
                    file_inventory = json.load(f)
            except Exception as e:
                logging.warning(f"Could not load file_inventory.json: {e}")
    
    # Calculate stats
    stats = calculate_dashboard_stats(uc_data, funding_data, risk_report)
    
    # Generate visualizations
    logging.info("Generating visualizations...")
    charts_generated = {}
    
    # 1. Bank Balance Cliff (only if funding data exists)
    try:
        charts_generated['bank_balance_cliff'] = generate_bank_balance_cliff_chart(
            uc_data, funding_data, output_path)
    except Exception as e:
        logging.error(f"Bank Balance Cliff failed: {e}")
        charts_generated['bank_balance_cliff'] = False
    
    # 2. Budget Heatmap
    try:
        charts_generated['budget_heatmap'] = generate_budget_heatmap(uc_data, output_path)
    except Exception as e:
        logging.error(f"Budget Heatmap failed: {e}")
        charts_generated['budget_heatmap'] = False
    
    # 3. Stacked Monthly Burn
    try:
        charts_generated['stacked_monthly_burn'] = generate_stacked_monthly_burn_chart(
            uc_data, output_path)
    except Exception as e:
        logging.error(f"Stacked Monthly Burn failed: {e}")
        charts_generated['stacked_monthly_burn'] = False
    
    # 4. Budget Flow Hierarchy
    try:
        charts_generated['budget_flow'] = generate_budget_flow_chart(uc_data, output_path)
    except Exception as e:
        logging.error(f"Budget Flow Hierarchy failed: {e}")
        charts_generated['budget_flow'] = False
    
    # 5. Improved Gantt Chart
    try:
        charts_generated['gantt_chart'] = generate_improved_gantt_chart(activity_data, output_path)
    except Exception as e:
        logging.error(f"Gantt Chart failed: {e}")
        charts_generated['gantt_chart'] = False
    
    # Generate markdown report
    report_path = generate_markdown_report(
        uc_data, funding_data, risk_report, stats,
        project_overview, output_path, file_inventory, charts_generated
    )
    
    # Summary
    logging.info("=" * 60)
    logging.info("✅ REPORT COMPLETE")
    logging.info(f"📄 Report: {report_path}")
    logging.info("📊 Visualizations:")
    for chart, success in charts_generated.items():
        status = "✓" if success else "✗"
        logging.info(f"   {status} {chart}")
    logging.info("=" * 60)
    
    return report_path


def main():
    """CLI entry point for standalone testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate project risk report')
    parser.add_argument('run_dir', help='Path to run directory')
    
    args = parser.parse_args()
    
    generate_full_report(run_dir=args.run_dir)


if __name__ == "__main__":
    main()
