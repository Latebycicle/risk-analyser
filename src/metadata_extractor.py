"""
Smart Metadata Filter for Excel Sheets

Intelligently extracts high-value text from Excel workbook sheets
while filtering out low-value noise.

Usage:
    from src.metadata_extractor import extract_smart_metadata
    
    metadata = extract_smart_metadata("path/to/excel.xlsx")
"""

import pandas as pd
import re
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import DATA_DIR, OLLAMA_URL, OLLAMA_MODEL
except ImportError:
    DATA_DIR = PROJECT_ROOT / "Data"
    OLLAMA_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "qwen3:4b"

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def clean_text_density(text):
    """Clean text by removing excessive whitespace."""
    cleaned = re.sub(r'[ \t]+', ' ', text)
    return cleaned.strip()


def check_sheet_relevance(sheet_name, text_snippet):
    """
    Use AI to determine if a sheet contains valuable project information.
    
    Args:
        sheet_name: Name of the Excel sheet
        text_snippet: First ~1000 chars of sheet content
        
    Returns:
        Boolean indicating if sheet is relevant
    """
    prompt = f"""Data Filter: Is this sheet strategic or operational?

Sheet: "{sheet_name}"
Content: "{text_snippet}..."

INCLUDE if: project overview, objectives, budget summary, compliance requirements
EXCLUDE if: detailed logs, batch schedules, attendance, detailed timelines

Return JSON: {{"relevant": true/false, "reason": "..."}}
"""
    
    schema = {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean"},
            "reason": {"type": "string"}
        },
        "required": ["relevant", "reason"]
    }
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "keep_alive": "5m",
            "options": {"temperature": 0.0, "num_ctx": 2048}
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        
        parsed = json.loads(result.get("response", "{}"))
        is_relevant = parsed.get('relevant', False)
        reason = parsed.get('reason', 'No reason')
        
        logging.info(f"  Relevance: {is_relevant} - {reason}")
        return is_relevant
        
    except Exception as e:
        logging.error(f"  Error checking relevance: {e}")
        return True  # Default to include on error


def extract_smart_metadata(excel_file_path):
    """
    Smart filter Excel sheets and extract valuable metadata.
    
    Args:
        excel_file_path: Path to the Excel file
        
    Returns:
        String containing filtered metadata
    """
    excel_file = Path(excel_file_path)
    
    if not excel_file.exists():
        logging.error(f"Excel file not found: {excel_file}")
        return ""
    
    logging.info(f"Loading Excel file: {excel_file}")
    xl_file = pd.ExcelFile(excel_file)
    all_sheets = xl_file.sheet_names
    
    logging.info(f"Found {len(all_sheets)} sheets")
    
    # Size threshold for auto-inclusion
    SIZE_THRESHOLD = 5000
    
    final_metadata = ""
    included_count = 0
    skipped_count = 0
    
    for sheet_name in all_sheets:
        logging.info(f"Processing: '{sheet_name}'")
        
        # Skip activity sheets (processed separately)
        if 'activity' in sheet_name.lower():
            logging.info("  ⊗ Skipping - Activity sheet")
            skipped_count += 1
            continue
        
        try:
            df = pd.read_excel(xl_file, sheet_name=sheet_name)
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            text = df.to_markdown(index=False) if hasattr(df, 'to_markdown') else df.to_string()
            cleaned_text = clean_text_density(text)
            
            if len(cleaned_text) < 50:
                logging.info("  ⊗ Skipping - Too small")
                skipped_count += 1
                continue
            
            # Auto-include small sheets or strategic-named sheets
            if (len(cleaned_text) < SIZE_THRESHOLD or 
                any(k in sheet_name.lower() for k in ['overview', 'summary', 'scope', 'objective'])):
                
                final_metadata += f"\n\n{'='*80}\nSHEET: {sheet_name}\n{'='*80}\n\n"
                final_metadata += cleaned_text
                included_count += 1
                logging.info(f"  ✓ INCLUDED - {len(cleaned_text):,} chars")
                continue
            
            # Skip obviously operational sheets
            if any(k in sheet_name.lower() for k in ['batch', 'attendance', 'tracking', 'log']):
                logging.info("  ⊗ Skipping - Operational")
                skipped_count += 1
                continue
            
            # AI check for large sheets
            if check_sheet_relevance(sheet_name, cleaned_text[:1000]):
                final_metadata += f"\n\n{'='*80}\nSHEET: {sheet_name}\n{'='*80}\n\n"
                final_metadata += cleaned_text
                included_count += 1
                logging.info(f"  ✓ INCLUDED (AI) - {len(cleaned_text):,} chars")
            else:
                skipped_count += 1
                logging.info("  ⊗ Skipping - Not relevant")
        
        except Exception as e:
            logging.error(f"  Error: {e}")
            skipped_count += 1
    
    logging.info(f"\nMetadata extraction complete!")
    logging.info(f"  Included: {included_count}, Skipped: {skipped_count}")
    logging.info(f"  Total chars: {len(final_metadata):,}")
    
    return final_metadata


if __name__ == "__main__":
    test_file = DATA_DIR / "Ivanti activity sheet_v2.xlsx"
    
    if not test_file.exists():
        test_file = Path("Data/Ivanti activity sheet_v2.xlsx")
    
    if test_file.exists():
        metadata = extract_smart_metadata(test_file)
        
        output_file = DATA_DIR / "smart_filtered_metadata.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(metadata)
        
        logging.info(f"Output saved to: {output_file}")
    else:
        logging.error(f"Test file not found: {test_file}")
