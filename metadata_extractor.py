"""
Smart Metadata Filter for Excel Sheets

This script intelligently extracts high-value text from Excel workbook sheets
while filtering out low-value noise like dropdown options, empty templates, etc.

Uses AI-powered relevance checking to determine which sheets contain strategic
project information worth including in metadata corpus.
"""

import pandas as pd
import re
import logging
import json
from pathlib import Path
from compliance_checker import call_ollama_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# File paths
EXCEL_FILE = Path("Data/Ivanti activity sheet_v2.xlsx")
OUTPUT_FILE = Path("smart_filtered_metadata.txt")


def clean_text_density(text):
    """
    Clean text by removing excessive whitespace while preserving structure.
    
    Args:
        text: Raw text string
        
    Returns:
        Cleaned text with normalized spacing
    """
    # Replace multiple horizontal spaces/tabs with single space
    # Preserves newlines to maintain table row structure
    cleaned = re.sub(r'[ \t]+', ' ', text)
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def check_sheet_relevance(sheet_name, text_snippet):
    """
    Use AI to determine if a sheet contains valuable project information.
    
    Args:
        sheet_name: Name of the Excel sheet
        text_snippet: First ~1000 chars of sheet content
        
    Returns:
        Boolean indicating if sheet is relevant
    """
    prompt = f"""You are a Data Filter for strategic project documentation.
Sheet Name: "{sheet_name}"
Content Snippet:
"{text_snippet}..."

Task: Determine if this sheet contains HIGH-LEVEL STRATEGIC information useful for management decisions.

INCLUDE if it contains:
- Project overview, objectives, or scope definition
- Key deliverables and success criteria
- Budget summary or funding information
- Compliance requirements or contractual obligations
- Strategic plans or executive summaries

EXCLUDE if it is:
- Detailed operational logs (batch schedules, daily tracking, detailed timelines)
- Large repetitive data tables (attendance sheets, detailed batch plans)
- Administrative templates or forms
- Granular execution-level details

Think: Would a senior manager or funder need this for strategic oversight?

Return JSON: {{"relevant": true/false, "reason": "..."}}
"""
    
    # Define structured output schema
    schema = {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean"},
            "reason": {"type": "string"}
        },
        "required": ["relevant", "reason"]
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
                "num_ctx": 2048
            }
        }
        
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        response_text = result.get("response", "")
        
        # Parse JSON
        parsed = json.loads(response_text)
        is_relevant = parsed.get('relevant', False)
        reason = parsed.get('reason', 'No reason provided')
        
        logging.info(f"  Relevance: {is_relevant} - {reason}")
        return is_relevant
        
    except Exception as e:
        logging.error(f"  Error checking relevance: {e}")
        # Default to including sheet if AI check fails
        return True


def main():
    """Main execution: Smart filter Excel sheets and extract valuable metadata."""
    
    logging.info("=" * 80)
    logging.info("SMART METADATA FILTER - EXCEL SHEET ANALYSIS")
    logging.info("=" * 80)
    
    if not EXCEL_FILE.exists():
        logging.error(f"Excel file not found: {EXCEL_FILE}")
        return
    
    # Load Excel file
    logging.info(f"Loading Excel file: {EXCEL_FILE}")
    xl_file = pd.ExcelFile(EXCEL_FILE)
    all_sheets = xl_file.sheet_names
    
    logging.info(f"Found {len(all_sheets)} sheets in workbook")
    logging.info("")
    
    # Statistics
    original_sheet_count = len(all_sheets)
    relevant_sheet_count = 0
    skipped_sheet_count = 0
    auto_included_count = 0
    final_metadata_corpus = ""
    
    # Size threshold: sheets under 5000 chars are auto-included (strategic, not bulk data)
    SIZE_THRESHOLD = 5000
    
    # Process each sheet
    for sheet_name in all_sheets:
        logging.info(f"Processing sheet: '{sheet_name}'")
        
        # Skip the Activity sheet (already parsed separately)
        if sheet_name == "Activity sheet ":
            logging.info("  ⊗ Skipping - Already processed separately")
            skipped_sheet_count += 1
            continue
        
        try:
            # Read sheet and convert to markdown (token-efficient format)
            df = pd.read_excel(xl_file, sheet_name=sheet_name)
            
            # For better readability, drop completely empty rows/columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            text = df.to_markdown(index=False)
            
            # Clean the text
            cleaned_text = clean_text_density(text)
            
            # Check if empty or too small
            if len(cleaned_text) < 50:
                logging.info("  ⊗ Skipping - Sheet too small/empty")
                skipped_sheet_count += 1
                continue
            
            # Size-based strategy: small sheets auto-include, large sheets need AI check
            if len(cleaned_text) < SIZE_THRESHOLD:
                # Small sheet - automatically include without AI check
                final_metadata_corpus += f"\n\n{'=' * 80}\n"
                final_metadata_corpus += f"SHEET: {sheet_name}\n"
                final_metadata_corpus += f"{'=' * 80}\n\n"
                final_metadata_corpus += cleaned_text
                
                auto_included_count += 1
                logging.info(f"  ✓ AUTO-INCLUDED (small sheet) - {len(cleaned_text):,} characters")
                continue
            
            # Large sheet - use AI to check relevance
            logging.info(f"  Large sheet ({len(cleaned_text):,} chars) - checking relevance...")
            
            # Special handling: sheets with "overview", "summary", or "scope" in name are highly likely strategic
            if any(keyword in sheet_name.lower() for keyword in ['overview', 'summary', 'scope', 'objective', 'deliverable']):
                logging.info(f"  Sheet name suggests strategic importance - auto-including")
                final_metadata_corpus += f"\n\n{'=' * 80}\n"
                final_metadata_corpus += f"SHEET: {sheet_name}\n"
                final_metadata_corpus += f"{'=' * 80}\n\n"
                final_metadata_corpus += cleaned_text
                
                relevant_sheet_count += 1
                logging.info(f"  ✓ INCLUDED (name-based) - {len(cleaned_text):,} characters added")
                continue
            
            # Skip obviously operational sheets by name
            if any(keyword in sheet_name.lower() for keyword in ['batch plan', 'batch schedule', 'attendance', 'tracking', 'log']):
                logging.info(f"  Sheet name suggests operational detail - skipping")
                skipped_sheet_count += 1
                continue
            
            # Take first 1000 chars as snippet for AI analysis
            snippet = cleaned_text[:1000]
            
            # AI relevance check
            is_relevant = check_sheet_relevance(sheet_name, snippet)
            
            if is_relevant:
                # Add entire cleaned text to corpus
                final_metadata_corpus += f"\n\n{'=' * 80}\n"
                final_metadata_corpus += f"SHEET: {sheet_name}\n"
                final_metadata_corpus += f"{'=' * 80}\n\n"
                final_metadata_corpus += cleaned_text
                
                relevant_sheet_count += 1
                logging.info(f"  ✓ INCLUDED (AI approved) - {len(cleaned_text):,} characters added")
            else:
                skipped_sheet_count += 1
                logging.info("  ⊗ Skipping - Not relevant")
        
        except Exception as e:
            logging.error(f"  Error processing sheet: {e}")
            skipped_sheet_count += 1
        
        logging.info("")
    
    # Save output
    logging.info("=" * 80)
    logging.info("SAVING FILTERED METADATA")
    logging.info("=" * 80)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_metadata_corpus)
    
    # Print statistics
    logging.info(f"\nMetadata filtering complete!")
    logging.info(f"  Original Sheets: {original_sheet_count}")
    logging.info(f"  Auto-Included (small): {auto_included_count}")
    logging.info(f"  AI-Approved (large): {relevant_sheet_count}")
    logging.info(f"  Skipped Sheets: {skipped_sheet_count}")
    logging.info(f"  Total Included: {auto_included_count + relevant_sheet_count}")
    logging.info(f"  Total Characters: {len(final_metadata_corpus):,}")
    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")
    logging.info("=" * 80)


if __name__ == "__main__":
    main()
