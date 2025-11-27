"""
Report Generator - Create Polished Markdown Reports

This module generates comprehensive risk and health reports in Markdown format,
including visualizations, statistics, and AI-powered strategic insights.

Output: Report/Project_Risk_Report.md (ready for PDF export via Obsidian)
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import shutil
from datetime import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path("Data")
REPORT_DIR = Path("Report")
REPORT_DIR.mkdir(exist_ok=True)


def load_analysis_data():
    """Load all analysis data from JSON files."""
    print("Loading analysis data...")
    
    with open(DATA_DIR / "uc_processed.json", 'r') as f:
        uc_data = json.load(f)
    
    with open(DATA_DIR / "funding_tranches_processed.json", 'r') as f:
        funding_data = json.load(f)
    
    with open(DATA_DIR / "master_risk_report.json", 'r') as f:
        risk_report = json.load(f)
    
    with open(DATA_DIR / "milestone_activities_processed.json", 'r') as f:
        milestone_data = json.load(f)
    
    project_metadata = parse_project_metadata()
    
    print(f"Loaded: {len(risk_report)} risks identified")
    return uc_data, funding_data, risk_report, milestone_data, project_metadata


def parse_project_metadata():
    """Parse the project_metadata.txt file to extract key overview details."""
    print("Parsing project metadata...")
    metadata_path = DATA_DIR / "smart_filtered_metadata.txt"
    metadata = {}
    
    if not metadata_path.exists():
        print("Warning: smart_filtered_metadata.txt not found.")
        # Return defaults
        return {
            "Title": "Skilling Program for Youth in IT-ITeS Sector",
            "Description": "A college-cum-community-based training program for 1,980 underserved youth in Hyderabad, Mumbai, and Bangalore. The program will be implemented through 9 colleges and 3 Express Training Centres (ETCs), delivering training in AI Productivity & Applications, followed by certification and placement support.",
            "Funder": "Ivanti Technology India Pvt. Ltd.",
            "Entity": "Sambhav Foundation",
            "Start Date": "1st September 2025",
            "End Date": "31st March 2026",
            "Region": "Mumbai, Bangalore & Hyderabad",
        }

    with open(metadata_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse the Project Overview section
    lines = content.split('\n')
    
    # Track if we've found the header row
    found_header = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Skip until we find the Project Overview section
        if 'SHEET: Project Overview' not in line and not found_header:
            continue
        
        # Check if this is the Field | Details header row
        if '| Field |' in line or '| Project overview |' in line:
            found_header = True
            continue
        
        if found_header and '|' in line and line_stripped:
            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]  # Remove empty parts
            
            if len(parts) >= 2:
                key = parts[0]
                value = parts[1]
                
                # Skip the header row and 'nan' values
                if key in ['Field', 'Project overview', ''] or value in ['Details', 'Unnamed: 1', 'nan', '']:
                    continue
                
                # Map the keys to metadata
                if 'Project Title' in key:
                    metadata['Project Title'] = value
                elif 'Brief Project Description' in key:
                    metadata['Brief Project Description'] = value
                elif 'Project Funder' in key:
                    metadata['Project Funder'] = value
                elif 'Project Entity' in key:
                    metadata['Project Entity'] = value
                elif 'MOU Effective Start Date' in key:
                    metadata['MOU Effective Start Date'] = value
                elif 'MOU End Date' in key:
                    metadata['MOU End Date'] = value
                elif 'Deployment Region' in key:
                    metadata['Deployment Region'] = value

    print(f"Parsed metadata keys: {list(metadata.keys())}")
    
    # Create project overview with fallbacks to actual data from the file
    project_overview = {
        "Title": metadata.get("Project Title", "Skilling Program for Youth in IT-ITeS Sector"),
        "Description": metadata.get("Brief Project Description", "A college-cum-community-based training program for 1,980 underserved youth in Hyderabad, Mumbai, and Bangalore. The program will be implemented through 9 colleges and 3 Express Training Centres (ETCs), delivering training in AI Productivity & Applications, followed by certification and placement support."),
        "Funder": metadata.get("Project Funder", "Ivanti Technology India Pvt. Ltd."),
        "Entity": metadata.get("Project Entity", "Sambhav Foundation"),
        "Start Date": metadata.get("MOU Effective Start Date", "1st September 2025"),
        "End Date": metadata.get("MOU End Date", "31st March 2026"),
        "Region": metadata.get("Deployment Region", "Mumbai, Bangalore & Hyderabad"),
    }
    return project_overview


def copy_cash_flow_graph():
    """Copy cash flow graph to Report folder."""
    source = DATA_DIR / "cash_flow_graph.png"
    dest = REPORT_DIR / "cash_flow_graph.png"
    
    if source.exists():
        shutil.copy(source, dest)
        print(f"Copied cash flow graph to {dest}")
    else:
        print(f"Warning: Cash flow graph not found at {source}")


def generate_budget_breakdown_chart(uc_data, output_folder=None):
    """
    Generate a horizontal bar chart of top 10 budget line items.
    
    Args:
        uc_data: UC processed data containing budget line totals
        output_folder: Path to save the chart (defaults to REPORT_DIR)
    """
    print("Generating budget breakdown chart...")
    
    if output_folder is None:
        output_folder = REPORT_DIR
    else:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    # Get budget line totals from nested structure and sort descending
    budget_lines = uc_data['budget_lines']
    budget_totals = {key: line['total_planned'] for key, line in budget_lines.items()}
    sorted_items = sorted(budget_totals.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_items[:10]
    
    # Prepare data
    labels = [item[0] for item in top_10]
    values = [item[1] for item in top_10]
    
    # Create horizontal bar chart
    plt.figure(figsize=(12, 8))
    colors = plt.cm.viridis(range(len(labels)))
    bars = plt.barh(labels, values, color=colors)
    
    # Styling
    plt.xlabel('Amount (₹)', fontsize=12, fontweight='bold')
    plt.title('Top 10 Budget Allocations', fontsize=16, fontweight='bold', pad=20)
    plt.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Add value labels on bars
    for i, (bar, value) in enumerate(zip(bars, values)):
        plt.text(value, bar.get_y() + bar.get_height()/2, 
                f' ₹{value:,.0f}', 
                va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    # Save
    output_path = output_folder / "budget_breakdown.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Budget breakdown chart saved to {output_path}")


def generate_monthly_spending_chart(uc_data):
    """
    Generate a line chart showing monthly planned spending over time.
    
    Args:
        uc_data: UC processed data containing monthly spending plan
    """
    print("Generating monthly spending trend chart...")
    
    monthly_data = uc_data['monthly_data']
    # Filter out zero-spend months
    months = [m for m in monthly_data.keys() if monthly_data[m]['planned'] > 0]
    values = [monthly_data[m]['planned'] for m in months]
    
    plt.figure(figsize=(14, 6))
    plt.plot(months, values, marker='o', linewidth=2, markersize=8, color='#2E86AB')
    plt.fill_between(range(len(months)), values, alpha=0.3, color='#2E86AB')
    
    # Styling
    plt.xlabel('Month', fontsize=12, fontweight='bold')
    plt.ylabel('Planned Spending (₹)', fontsize=12, fontweight='bold')
    plt.title('Monthly Spending Trend', fontsize=16, fontweight='bold', pad=20)
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Format y-axis to show currency
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1000:.0f}K'))
    
    plt.tight_layout()
    
    output_path = REPORT_DIR / "monthly_spending_trend.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Monthly spending trend chart saved to {output_path}")


def generate_category_spending_chart(uc_data):
    """
    Generate a stacked bar chart showing spending by category over time.
    
    Args:
        uc_data: UC processed data containing budget line monthly plans
    """
    print("Generating category spending breakdown chart...")
    
    # Extract budget lines with monthly plans from nested structure
    budget_lines = uc_data['budget_lines']
    budget_line_monthly = {key: line['monthly_data'] for key, line in budget_lines.items()}
    
    # Categorize budget lines
    categories = {
        'Salaries': [],
        'Training & Assessment': [],
        'Operational Costs': [],
        'Other': []
    }
    
    for line_item in budget_line_monthly.keys():
        if 'Salary' in line_item:
            categories['Salaries'].append(line_item)
        elif 'Training Aids' in line_item or 'Assessment' in line_item:
            categories['Training & Assessment'].append(line_item)
        elif 'Operational Cost' in line_item:
            categories['Operational Costs'].append(line_item)
        else:
            categories['Other'].append(line_item)
    
    # Get months and filter out zero-spend months
    all_months = list(uc_data['monthly_data'].keys())
    months = [m for m in all_months if uc_data['monthly_data'][m]['planned'] > 0]
    
    # Calculate category totals per month
    category_data = {}
    for cat_name, line_items in categories.items():
        category_data[cat_name] = []
        for month in months:
            total = sum(budget_line_monthly[item][month]['planned'] for item in line_items)
            category_data[cat_name].append(total)
    
    # Create stacked bar chart
    fig, ax = plt.subplots(figsize=(14, 8))
    
    bottom = [0] * len(months)
    colors = ['#E63946', '#F77F00', '#06AED5', '#118AB2']
    
    for i, (cat_name, values) in enumerate(category_data.items()):
        ax.bar(months, values, bottom=bottom, label=cat_name, color=colors[i])
        bottom = [bottom[j] + values[j] for j in range(len(months))]
    
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Spending (₹)', fontsize=12, fontweight='bold')
    ax.set_title('Monthly Spending by Category', fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper left')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1000:.0f}K'))
    
    plt.tight_layout()
    
    output_path = REPORT_DIR / "category_spending_breakdown.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Category spending breakdown chart saved to {output_path}")


def generate_cash_flow_table(uc_data, funding_data):
    """
    Generate cash flow analysis data table.
    
    Args:
        uc_data: UC processed data
        funding_data: Funding tranches data
        
    Returns:
        List of dictionaries with monthly cash flow data
    """
    print("Generating cash flow table data...")
    
    from datetime import datetime
    
    all_months = list(uc_data['cumulative_data'].keys())
    # Filter out zero-spend months
    months = [m for m in all_months if uc_data['monthly_data'][m]['planned'] > 0]
    
    # Build cumulative funding map
    cumulative_funding_map = {}
    running_total = 0
    
    for month in all_months:
        for tranche in funding_data['tranches']:
            tranche_date_str = tranche['expected_billing_date_str'].split()[0]
            tranche_date = datetime.strptime(tranche_date_str, '%Y-%m-%d')
            tranche_month = tranche_date.strftime('%b-%y')
            
            month_normalized = month.replace(' ', '-')
            
            if tranche_month == month_normalized and running_total < sum(
                t['billing_value'] for t in funding_data['tranches'] 
                if datetime.strptime(t['expected_billing_date_str'].split()[0], '%Y-%m-%d') <= tranche_date
            ):
                running_total += tranche['billing_value']
        
        cumulative_funding_map[month] = running_total
    
    # Build table data
    table_data = []
    for month in months:
        monthly_spend = uc_data['monthly_data'][month]['planned']
        cumulative_spend = uc_data['cumulative_data'][month]['cumulative_planned']
        cumulative_funding = cumulative_funding_map[month]
        cash_available = cumulative_funding - cumulative_spend
        
        table_data.append({
            'month': month,
            'monthly_spend': monthly_spend,
            'cumulative_spend': cumulative_spend,
            'cumulative_funding': cumulative_funding,
            'cash_available': cash_available
        })
    
    return table_data




def generate_risk_severity_pie_chart(risk_report):
    """
    Generate a pie chart showing distribution of risks by severity.
    
    Args:
        risk_report: Master risk report
    """
    print("Generating risk severity distribution chart...")
    
    # Count risks by severity
    severity_counts = {}
    for risk in risk_report:
        severity = risk.get('severity', 'Unknown')
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    if not severity_counts:
        print("No risks to chart")
        return
    
    labels = list(severity_counts.keys())
    sizes = list(severity_counts.values())
    colors = ['#E63946', '#F77F00', '#06AED5', '#DDDDDD'][:len(labels)]
    explode = [0.1 if label == 'High' else 0 for label in labels]
    
    plt.figure(figsize=(10, 8))
    plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.0f%%',
            shadow=True, startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
    plt.title('Risk Distribution by Severity', fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    output_path = REPORT_DIR / "risk_severity_distribution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Risk severity distribution chart saved to {output_path}")


def calculate_dashboard_stats(uc_data, funding_data, risk_report):
    """
    Calculate key dashboard statistics with graceful handling of missing data.
    
    Args:
        uc_data: UC processed data (can be None)
        funding_data: Funding tranches data (can be None)
        risk_report: Master risk report
    
    Returns:
        Dictionary with dashboard metrics ("N/A" for missing data)
    """
    print("Calculating dashboard statistics...")
    
    # Handle missing funding data
    if funding_data is None or not funding_data:
        total_value = 0.0
        print("  ⚠ Funding data missing - setting total value to 0")
    else:
        total_value = funding_data.get('total_billing_value', 0)
    
    # Handle missing UC data
    if uc_data is None or not uc_data:
        duration = 0
        avg_monthly_burn = 0.0
        highest_cost_name = "N/A"
        highest_cost_value = 0.0
        print("  ⚠ UC data missing - setting duration and costs to 0")
    else:
        # Project Duration (months)
        duration = len(uc_data.get('monthly_data', {}))
        
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
    
    # Risk Score (count of High/Medium risks)
    high_risks = sum(1 for r in risk_report if str(r.get('severity', '')).lower() == 'high')
    medium_risks = sum(1 for r in risk_report if str(r.get('severity', '')).lower() == 'medium')
    total_risks = len(risk_report)
    
    stats = {
        'total_value': total_value,
        'duration': duration,
        'avg_monthly_burn': avg_monthly_burn,
        'highest_cost_name': highest_cost_name,
        'highest_cost_value': highest_cost_value,
        'high_risks': high_risks,
        'medium_risks': medium_risks,
        'total_risks': total_risks
    }
    
    print(f"Stats: {total_risks} risks ({high_risks} High, {medium_risks} Medium)")
    return stats


def generate_risk_type_distribution_chart(risk_report):
    """
    Generate a bar chart showing distribution of risks by type.
    
    Args:
        risk_report: Master risk report
    """
    print("Generating risk type distribution chart...")
    
    risk_type_counts = {}
    for risk in risk_report:
        risk_type = risk.get('risk_type', 'Unknown')
        risk_type_counts[risk_type] = risk_type_counts.get(risk_type, 0) + 1
        
    if not risk_type_counts:
        print("No risks to chart by type.")
        return

    labels = list(risk_type_counts.keys())
    values = list(risk_type_counts.values())
    
    plt.figure(figsize=(12, 7))
    colors = plt.cm.plasma(range(len(labels)))
    bars = plt.bar(labels, values, color=colors)
    
    plt.ylabel('Number of Risks', fontsize=12, fontweight='bold')
    plt.title('Risk Distribution by Type', fontsize=16, fontweight='bold', pad=20)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center')

    plt.tight_layout()
    
    output_path = REPORT_DIR / "risk_type_distribution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Risk type distribution chart saved to {output_path}")


def generate_gantt_chart(milestone_data):
    """
    Generate a Gantt chart for project milestones.
    
    Args:
        milestone_data: Processed milestone activities data.
    """
    print("Generating Gantt chart for project milestones...")
    
    activities = []
    for category, tasks in milestone_data.items():
        for task in tasks:
            activities.append({
                'category': category,
                'activity': task['activity'],
                'start': datetime.fromisoformat(task['start_date_iso']),
                'end': datetime.fromisoformat(task['end_date_iso']),
                'duration': task['duration_in_days']
            })

    if not activities:
        print("No activities to create a Gantt chart.")
        return

    df = pd.DataFrame(activities)
    df = df.sort_values(by='start', ascending=False)
    
    # Make the chart much bigger and add more spacing
    fig, ax = plt.subplots(figsize=(20, 16))
    
    categories = df['category'].unique()
    colors = plt.cm.viridis([i/len(categories) for i in range(len(categories))])
    color_map = dict(zip(categories, colors))

    # Add spacing between bars
    y_positions = range(len(df))
    bar_height = 0.7  # Make bars slightly thinner to add visual spacing
    
    for i, (idx, task) in enumerate(df.iterrows()):
        start_date = task['start']
        end_date = task['end']
        duration = (end_date - start_date).days
        ax.barh(y_positions[i], duration, left=start_date, height=bar_height, 
                color=color_map[task['category']], edgecolor='white', linewidth=0.5)

    # Set y-axis labels with better spacing
    ax.set_yticks(y_positions)
    ax.set_yticklabels([task['activity'][:80] + ('...' if len(task['activity']) > 80 else '') 
                        for _, task in df.iterrows()], fontsize=9)
    
    ax.xaxis_date()
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.title('Project Milestones Gantt Chart', fontsize=20, fontweight='bold', pad=25)
    plt.xlabel('Date', fontsize=14, fontweight='bold')
    plt.grid(axis='x', linestyle='--', alpha=0.4)
    
    # Create a legend for categories
    patches = [plt.Rectangle((0,0),1,1, color=color_map[cat]) for cat in categories]
    plt.legend(patches, categories, bbox_to_anchor=(1.02, 1), loc='upper left', 
               borderaxespad=0., fontsize=10, framealpha=0.9)

    plt.tight_layout(rect=[0, 0, 0.88, 1])
    
    output_path = REPORT_DIR / "project_gantt_chart.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close()
    
    print(f"Gantt chart saved to {output_path}")


def generate_markdown_report(uc_data, funding_data, risk_report, stats, project_overview, cash_flow_table, output_folder=None, file_inventory=None):
    """
    Generate comprehensive Markdown report with graceful handling of missing data.
    
    Args:
        uc_data: UC processed data
        funding_data: Funding tranches data (can be None)
        risk_report: Master risk report
        stats: Dashboard statistics
        project_overview: Parsed project overview from metadata
        cash_flow_table: Monthly cash flow details
        output_folder: Path to save the report (defaults to REPORT_DIR)
        file_inventory: Dictionary with identified file paths from ProjectLoader
    """
    print("Generating Markdown report...")
    
    if output_folder is None:
        output_folder = REPORT_DIR
    else:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    report_path = output_folder / "Project_Risk_Report.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        # Title
        f.write("# Project Risk & Health Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n")
        f.write("---\n\n")

        # Project Overview
        f.write("## Project Overview\n\n")
        f.write(f"**{project_overview.get('Title', 'Skilling Program for Youth in IT-ITeS Sector')}**\n\n")
        
        description = project_overview.get('Description', 'N/A')
        if len(description) > 200:
            # Wrap long descriptions
            f.write(f"{description}\n\n")
        else:
            f.write(f"**Description:** {description}\n\n")
        
        f.write("| **Field** | **Details** |\n")
        f.write("|-----------|-------------|\n")
        f.write(f"| **Funder** | {project_overview.get('Funder', 'N/A')} |\n")
        f.write(f"| **Implementing Entity** | {project_overview.get('Entity', 'N/A')} |\n")
        f.write(f"| **Deployment Region** | {project_overview.get('Region', 'N/A')} |\n")
        f.write(f"| **Project Period** | {project_overview.get('Start Date', 'N/A')} to {project_overview.get('End Date', 'N/A')} |\n")
        f.write(f"| **Total Budget** | ₹{stats['total_value']:,.2f} |\n")
        f.write(f"| **Duration** | {stats['duration']} months |\n\n")
        
        # Executive Dashboard
        f.write("## Executive Dashboard\n\n")
        f.write("### Key Metrics at a Glance\n\n")
        f.write("| **Metric** | **Value** |\n")
        f.write("|------------|----------|\n")
        f.write(f"| Total Project Value | ₹{stats['total_value']:,.2f} |\n")
        f.write(f"| Project Duration | {stats['duration']} months |\n")
        f.write(f"| Average Monthly Burn Rate | ₹{stats['avg_monthly_burn']:,.2f} |\n")
        f.write(f"| Highest Cost Item | {stats['highest_cost_name'][:50]}{'...' if len(stats['highest_cost_name']) > 50 else ''} (₹{stats['highest_cost_value']:,.0f}) |\n")
        f.write(f"| **Total Risks Identified** | **{stats['total_risks']}** |\n")
        f.write(f"| High Severity Risks | {stats['high_risks']} |\n")
        f.write(f"| Medium Severity Risks | {stats['medium_risks']} |\n\n")
        
        f.write("---\n\n")
        
        # Financial Analysis
        f.write("## Financial Health Analysis\n\n")
        
        f.write("### Cash Flow Analysis\n\n")
        
        # Handle missing funding data gracefully
        if funding_data is None or not funding_data:
            f.write("> *Insufficient data to generate cash flow analysis.*\n\n")
            f.write("> **Note:** Funding/billing data was not available for this analysis. ")
            f.write("Please ensure billing tracker data is provided for complete financial insights.\n\n")
        else:
            f.write("The cash flow graph below shows the cumulative funding availability versus planned spending:\n\n")
            f.write('<img src="cash_flow_graph.png" width="600">\n\n')
        
        f.write("### Monthly Cash Flow Details\n\n")
        f.write("| **Month** | **Monthly Spend** | **Cumulative Spend** | **Cumulative Funding** | **Cash Available** |\n")
        f.write("|-----------|------------------:|---------------------:|-----------------------:|-------------------:|\n")
        
        for row in cash_flow_table:
            status_emoji = "✅" if row['cash_available'] >= 0 else "⚠️"
            f.write(f"| {row['month']} | ₹{row['monthly_spend']:,.0f} | ₹{row['cumulative_spend']:,.0f} | ₹{row['cumulative_funding']:,.0f} | {status_emoji} ₹{row['cash_available']:,.0f} |\n")
        
        f.write("\n")
        
        f.write("### Monthly Spending Pattern\n\n")
        f.write('<img src="monthly_spending_trend.png" width="600">\n\n')
        
        f.write("### Budget Allocation by Category\n\n")
        f.write('<img src="category_spending_breakdown.png" width="600">\n\n')
        
        f.write("### Top Budget Line Items\n\n")
        f.write('<img src="budget_breakdown.png" width="600">\n\n')
        
        # Project Timeline
        f.write("## Project Timeline & Milestones\n\n")
        f.write("The Gantt chart below illustrates major activities and their timelines:\n\n")
        f.write("![Project Gantt Chart](project_gantt_chart.png)\n\n")

        # Risk Register
        f.write("## Risk Register\n\n")
        f.write("### Risk Distribution Overview\n\n")
        
        f.write('<table>\n')
        f.write('<tr>\n')
        f.write('<td width="50%">\n\n')
        f.write('<img src="risk_severity_distribution.png" width="400">\n\n')
        f.write('</td>\n')
        f.write('<td width="50%">\n\n')
        f.write('<img src="risk_type_distribution.png" width="400">\n\n')
        f.write('</td>\n')
        f.write('</tr>\n')
        f.write('</table>\n\n')
        
        f.write("---\n\n")

        f.write("### Detailed Risk Analysis\n\n")
        f.write("| **Risk Type** | **Severity** | **Details** |\n")
        f.write("|---------------|--------------|-------------|\n")
        
        for risk in risk_report:
            risk_type = risk.get('risk_type', 'Unknown')
            severity = risk.get('severity', 'Unknown')
            
            # Add emoji based on severity
            if severity == 'High':
                severity_display = "High"
            elif severity == 'Medium':
                severity_display = "Medium"
            else:
                severity_display = f"{severity}"
            
            # Get details (handle different risk structures)
            if 'month' in risk:
                details = f"**Month:** {risk['month']}<br/>{risk.get('details', '')}"
            elif 'activity' in risk:
                details = f"**Activity:** {risk['activity']}<br/>{risk.get('details', '')}"
            else:
                details = risk.get('details', 'No details provided')
            
            # Escape pipe characters and clean text
            details_clean = details.replace('|', '\\|').replace('\n', '<br/>')
            risk_type_clean = risk_type.replace('|', '\\|')
            
            # No truncation - show full risk details
            
            f.write(f"| {risk_type_clean} | {severity_display} | {details_clean} |\n")
        
        f.write("\n")
        
        # Strategic Observations
        f.write("## Strategic AI Analysis\n\n")
        f.write("AI-powered strategic risk audit identified the following high-level concerns:\n\n")
        
        strategic_risks = [r for r in risk_report if 'Strategic' in r.get('risk_type', '')]
        
        if strategic_risks:
            for i, risk in enumerate(strategic_risks, 1):
                severity = risk.get('severity', 'Unknown')
                
                f.write(f"### Risk #{i}: {risk.get('risk_type', 'Strategic Risk')}\n\n")
                f.write(f"**Severity:** {severity}\n\n")
                f.write(f"{risk.get('details', 'No details provided')}\n\n")
        else:
            f.write("*No strategic risks identified in this analysis.*\n\n")
        
        f.write("---\n\n")
        
        # Footer
        f.write("## Recommendations & Next Steps\n\n")
        f.write("Based on the analysis above:\n\n")
        f.write("1. **Immediate Action Required:** Review all High severity risks and develop mitigation strategies\n")
        f.write("2. **Financial Monitoring:** Track actual spending against planned budget monthly\n")
        f.write("3. **Risk Mitigation:** Address activity-budget mapping gaps identified\n")
        f.write("4. **Compliance:** Ensure post-placement tracking mechanisms are in place\n\n")
        
        f.write("---\n\n")
        
        # Data Sources Section
        f.write("## 📂 Data Sources Analyzed\n\n")
        
        if file_inventory:
            f.write("### Primary Project Files\n\n")
            f.write("| **File Type** | **Filename** | **Status** |\n")
            f.write("|---------------|--------------|------------|\n")
            
            # UC File
            uc_file = Path(file_inventory.get('uc', '')).name if file_inventory.get('uc') else 'N/A'
            uc_status = '✓ Found' if file_inventory.get('uc') else '✗ Missing'
            f.write(f"| UC/Budget | `{uc_file}` | {uc_status} |\n")
            
            # Activity File
            activity_file = Path(file_inventory.get('activity', '')).name if file_inventory.get('activity') else 'N/A'
            activity_status = '✓ Found' if file_inventory.get('activity') else '✗ Missing'
            f.write(f"| Activity/Plan | `{activity_file}` | {activity_status} |\n")
            
            # Billing File
            billing_file = Path(file_inventory.get('billing', '')).name if file_inventory.get('billing') else 'N/A'
            billing_status = '✓ Found' if file_inventory.get('billing') else '✗ Missing'
            f.write(f"| Billing/Tracker | `{billing_file}` | {billing_status} |\n\n")
            
            # Context Files
            context_files = file_inventory.get('context', [])
            if context_files:
                f.write("### Additional Context Files\n\n")
                for ctx_file in context_files:
                    ctx_filename = Path(ctx_file).name
                    f.write(f"- `{ctx_filename}`\n")
                f.write("\n")
            
            # Analysis outputs section
            f.write("### Generated Analysis Files\n\n")
            f.write("The following files were generated during this analysis:\n\n")
            f.write("- `uc_processed.json` - Processed budget and utilization certificate data\n")
            f.write("- `milestone_activities_processed.json` - Extracted milestones and activities\n")
            if Path('Data/funding_tranches_processed.json').exists():
                f.write("- `funding_tranches_processed.json` - Funding tranche information\n")
            f.write("- `master_risk_report.json` - Complete risk analysis results\n\n")
        else:
            f.write("**Data Sources:**\n")
            f.write("- Financial data from UC and billing trackers\n")
            f.write("- Activity timelines and milestone schedules\n")
            f.write("- AI-powered compliance and strategic risk analysis\n\n")
        
        f.write("---\n\n")
        f.write("## Report Metadata\n\n")
        f.write(f"**Report Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
        f.write(f"**Analysis Engine:** Risk Analyzer v2.0\n")
        f.write(f"**AI Model:** Ollama qwen3:4b (local)\n\n")
        f.write("---\n\n")
        f.write("*End of Report*\n")
    
    print(f"Markdown report generated at {report_path}")


def main(output_folder=None, file_inventory=None):
    """
    Main execution: Generate complete report.
    
    Args:
        output_folder: Path to save report and visualizations (defaults to REPORT_DIR)
        file_inventory: Dictionary with identified file paths from ProjectLoader
    """
    print("=" * 80)
    print("REPORT GENERATOR - Starting")
    print("=" * 80)
    
    # Try to load file inventory from JSON if not provided
    if file_inventory is None:
        file_inventory_path = Path('Data/file_inventory.json')
        if file_inventory_path.exists():
            try:
                with open(file_inventory_path, 'r', encoding='utf-8') as f:
                    file_inventory = json.load(f)
                print(f"Loaded file inventory from {file_inventory_path}")
            except Exception as e:
                print(f"Warning: Could not load file_inventory.json: {e}")
    
    if output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"Output folder: {output_path}")
    else:
        output_path = REPORT_DIR
    
    # Step 1: Setup & Load Data
    uc_data, funding_data, risk_report, milestone_data, project_overview = load_analysis_data()
    copy_cash_flow_graph()
    
    # Step 2: Generate Visuals
    generate_budget_breakdown_chart(uc_data, output_path)
    generate_monthly_spending_chart(uc_data)
    generate_category_spending_chart(uc_data)
    generate_risk_severity_pie_chart(risk_report)
    generate_risk_type_distribution_chart(risk_report)
    generate_gantt_chart(milestone_data)
    
    # Step 3: Generate Cash Flow Table
    cash_flow_table = generate_cash_flow_table(uc_data, funding_data)
    
    # Step 4: Calculate Stats
    stats = calculate_dashboard_stats(uc_data, funding_data, risk_report)
    
    # Step 5: Generate Markdown Report
    generate_markdown_report(uc_data, funding_data, risk_report, stats, project_overview, cash_flow_table, output_path, file_inventory)
    
    print("\n" + "=" * 80)
    print(f"✅ REPORT COMPLETE")
    print(f"📄 Report: {output_path / 'Project_Risk_Report.md'}")
    print(f"📊 Visualizations generated:")
    print(f"   - Cash flow graph")
    print(f"   - Budget breakdown chart")
    print(f"   - Monthly spending trend")
    print(f"   - Category spending breakdown")
    print(f"   - Risk severity distribution")
    print(f"   - Risk type distribution")
    print(f"   - Project Gantt chart")
    print("=" * 80)


if __name__ == "__main__":
    main()
