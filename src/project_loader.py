"""
Project Loader Module

Robustly identifies project files in a target folder and extracts text context.

Features:
- Automatic file identification using heuristic keyword matching
- Handles conflicts with priority-based resolution
- Extracts text from PDFs, Excel, DOCX, and TXT files
- Returns structured context for AI analysis

Dependencies: os, glob, pandas, pypdf, logging
"""

import os
import glob
import logging
import pandas as pd
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Optional: Import pypdf if available
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    logging.warning("pypdf not installed. PDF extraction will be skipped. Install with: pip install pypdf")
    PYPDF_AVAILABLE = False

# Optional: Import python-docx if available
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    logging.warning("python-docx not installed. DOCX extraction will be skipped. Install with: pip install python-docx")
    DOCX_AVAILABLE = False


class ProjectLoader:
    """
    Robustly identifies project files and extracts context from a target folder.
    
    File Identification Heuristics:
    - UC: Contains "UC", "Utilization", or "Budget"
    - Activity: Contains "Activity", "Plan", or "Timeline"
    - Billing: Contains "Billing", "Tracker", or "Tranche"
    - Context: Any other .pdf, .xlsx, .docx, or .txt files
    
    Attributes:
        folder_path: Path to the project folder
        files: Dictionary containing identified file paths
            - 'uc': UC/Budget file path
            - 'activity': Activity/Plan file path
            - 'billing': Billing/Tracker file path
            - 'context': List of additional files for context extraction
    """
    
    # Priority order for conflict resolution (higher number = higher priority)
    FILE_TYPE_PRIORITY = {
        'uc': 3,
        'billing': 2,
        'activity': 1
    }
    
    def __init__(self, folder_path):
        """
        Initialize the ProjectLoader.
        
        Args:
            folder_path: Path to the folder containing project files
            
        Raises:
            ValueError: If folder doesn't exist
        """
        self.folder_path = Path(folder_path)
        
        if not self.folder_path.exists():
            raise ValueError(f"Folder not found: {folder_path}")
        
        if not self.folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        self.files = {
            'uc': None,
            'activity': None,
            'billing': None,
            'context': []
        }
        
        logging.info(f"ProjectLoader initialized for: {self.folder_path.resolve()}")
    
    def identify_files(self):
        """
        Scan the folder and identify files using heuristic keyword matching.
        
        Identification Rules (case-insensitive):
        - UC: "UC", "Utilization", "Budget"
        - Activity: "Activity", "Plan", "Timeline"
        - Billing: "Billing", "Tracker", "Tranche"
        - Context: Other supported files (.pdf, .xlsx, .docx, .txt)
        
        Handles conflicts by prioritizing based on specificity (UC > Billing > Activity).
        
        Returns:
            Dictionary with identified file paths
        """
        logging.info("Scanning folder for project files...")
        
        # Define keywords for each file type
        keywords = {
            'uc': ['uc', 'utilization', 'budget'],
            'activity': ['activity', 'plan', 'timeline'],
            'billing': ['billing', 'tracker', 'tranche']
        }
        
        # Supported extensions for context files
        context_extensions = ['.pdf', '.xlsx', '.xls', '.xlsm', '.docx', '.txt']
        
        # Scan all files in the folder
        all_files = list(self.folder_path.glob('*'))
        
        for file_path in all_files:
            if not file_path.is_file():
                continue
            
            filename = file_path.name
            filename_lower = filename.lower()
            file_ext = file_path.suffix.lower()
            
            # Skip unsupported file types for project files
            if file_ext not in context_extensions and file_ext not in ['.xlsx', '.xls', '.xlsm']:
                continue
            
            # Check which categories this file matches
            matches = []
            for file_type, keyword_list in keywords.items():
                for keyword in keyword_list:
                    if keyword in filename_lower:
                        matches.append(file_type)
                        break  # Only count each file_type once
            
            # Handle file categorization
            if len(matches) == 0:
                # No keyword match - add to context
                self.files['context'].append(str(file_path.resolve()))
                logging.info(f"  ⊕ Context file: {filename}")
            
            elif len(matches) == 1:
                # Clear match - assign to appropriate category
                file_type = matches[0]
                self.files[file_type] = str(file_path.resolve())
                logging.info(f"  ✓ {file_type.upper()} file identified: {filename}")
            
            else:
                # Multiple matches - resolve by priority
                prioritized = sorted(matches, key=lambda x: self.FILE_TYPE_PRIORITY[x], reverse=True)
                chosen_type = prioritized[0]
                self.files[chosen_type] = str(file_path.resolve())
                logging.warning(
                    f"  ⚠ File '{filename}' matches multiple categories {matches}. "
                    f"Assigned to '{chosen_type}' (highest priority)."
                )
        
        # Summary
        logging.info("\n" + "="*60)
        logging.info("File Identification Summary:")
        logging.info("="*60)
        logging.info(f"  UC File:       {Path(self.files['uc']).name if self.files['uc'] else '❌ NOT FOUND'}")
        logging.info(f"  Activity File: {Path(self.files['activity']).name if self.files['activity'] else '❌ NOT FOUND'}")
        logging.info(f"  Billing File:  {Path(self.files['billing']).name if self.files['billing'] else '❌ NOT FOUND'}")
        logging.info(f"  Context Files: {len(self.files['context'])} found")
        
        if self.files['context']:
            for ctx_file in self.files['context']:
                logging.info(f"    - {Path(ctx_file).name}")
        
        logging.info("="*60)
        
        return self.files
    
    def load_context_text(self):
        """
        Extract text content from all context files.
        
        Supported Formats:
        - PDF: Extracted using pypdf (if installed)
        - Excel: All sheets converted to markdown-style tables
        - DOCX: Paragraphs extracted as plain text
        - TXT: Read directly
        
        Returns:
            Tuple of (combined_context_string, list_of_source_filenames)
        """
        if not self.files['context']:
            logging.info("No context files to extract")
            return "", []
        
        logging.info(f"\n{'='*60}")
        logging.info(f"Extracting text from {len(self.files['context'])} context files...")
        logging.info(f"{'='*60}")
        
        combined_text = ""
        source_files = []
        
        for file_path in self.files['context']:
            file_path_obj = Path(file_path)
            filename = file_path_obj.name
            file_ext = file_path_obj.suffix.lower()
            
            try:
                # Extract based on file type
                if file_ext == '.pdf':
                    if not PYPDF_AVAILABLE:
                        logging.warning(f"  ⊗ Skipping PDF (pypdf not installed): {filename}")
                        continue
                    
                    logging.info(f"  → Extracting PDF: {filename}")
                    text = self._extract_pdf_text(file_path)
                    combined_text += f"\n\n{'='*60}\n"
                    combined_text += f"SOURCE: {filename} (PDF)\n"
                    combined_text += f"{'='*60}\n{text}\n"
                    source_files.append(filename)
                
                elif file_ext in ['.xlsx', '.xls', '.xlsm']:
                    logging.info(f"  → Extracting Excel: {filename}")
                    text = self._extract_excel_text(file_path)
                    combined_text += f"\n\n{'='*60}\n"
                    combined_text += f"SOURCE: {filename} (Excel)\n"
                    combined_text += f"{'='*60}\n{text}\n"
                    source_files.append(filename)
                
                elif file_ext == '.docx':
                    if not DOCX_AVAILABLE:
                        logging.warning(f"  ⊗ Skipping DOCX (python-docx not installed): {filename}")
                        continue
                    
                    logging.info(f"  → Extracting DOCX: {filename}")
                    text = self._extract_docx_text(file_path)
                    combined_text += f"\n\n{'='*60}\n"
                    combined_text += f"SOURCE: {filename} (Word Document)\n"
                    combined_text += f"{'='*60}\n{text}\n"
                    source_files.append(filename)
                
                elif file_ext == '.txt':
                    logging.info(f"  → Reading TXT: {filename}")
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    combined_text += f"\n\n{'='*60}\n"
                    combined_text += f"SOURCE: {filename} (Text File)\n"
                    combined_text += f"{'='*60}\n{text}\n"
                    source_files.append(filename)
                
            except Exception as e:
                logging.error(f"  ✗ Error extracting {filename}: {e}")
                continue
        
        logging.info(f"\n{'='*60}")
        logging.info(f"Context Extraction Complete")
        logging.info(f"  Files processed: {len(source_files)}")
        logging.info(f"  Total characters: {len(combined_text):,}")
        logging.info(f"{'='*60}\n")
        
        return combined_text, source_files
    
    def _extract_pdf_text(self, file_path):
        """
        Extract text from a PDF file using pypdf.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        reader = PdfReader(file_path)
        text = ""
        
        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text()
                text += f"\n--- Page {page_num} ---\n{page_text}\n"
            except Exception as e:
                logging.warning(f"    Error extracting page {page_num}: {e}")
                continue
        
        return text
    
    def _extract_excel_text(self, file_path):
        """
        Extract text from all sheets in an Excel file.
        Converts DataFrames to markdown-style string representation.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            Extracted text as string
        """
        xl_file = pd.ExcelFile(file_path)
        text = ""
        
        for sheet_name in xl_file.sheet_names:
            try:
                df = pd.read_excel(xl_file, sheet_name=sheet_name)
                text += f"\n--- Sheet: {sheet_name} ---\n"
                text += f"Shape: {df.shape[0]} rows × {df.shape[1]} columns\n\n"
                # Convert to markdown-style table (cleaner than to_string())
                text += df.to_markdown(index=False) if hasattr(df, 'to_markdown') else df.to_string()
                text += "\n"
            except Exception as e:
                logging.warning(f"    Could not read sheet '{sheet_name}': {e}")
                continue
        
        return text
    
    def _extract_docx_text(self, file_path):
        """
        Extract text from a Word document (.docx).
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Extracted text as string
        """
        doc = Document(file_path)
        text = ""
        
        for para_num, paragraph in enumerate(doc.paragraphs, 1):
            para_text = paragraph.text.strip()
            if para_text:  # Skip empty paragraphs
                text += para_text + "\n"
        
        return text
    
    def get_summary(self):
        """
        Get a summary of identified files and project readiness.
        
        Returns:
            Dictionary with file counts and status
        """
        return {
            'uc_found': self.files['uc'] is not None,
            'activity_found': self.files['activity'] is not None,
            'billing_found': self.files['billing'] is not None,
            'context_files_count': len(self.files['context']),
            'ready_for_analysis': all([
                self.files['uc'],
                self.files['activity'],
                self.files['billing']
            ]),
            'uc_path': self.files['uc'],
            'activity_path': self.files['activity'],
            'billing_path': self.files['billing']
        }


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # Allow folder path as command line argument
    folder = sys.argv[1] if len(sys.argv) > 1 else "Data"
    
    print(f"\n{'='*70}")
    print(f"PROJECT LOADER - Testing with folder: {folder}")
    print(f"{'='*70}\n")
    
    try:
        # Initialize loader
        loader = ProjectLoader(folder)
        
        # Step 1: Identify files
        files = loader.identify_files()
        
        # Step 2: Extract context
        context_text, source_files = loader.load_context_text()
        
        # Step 3: Show summary
        summary = loader.get_summary()
        
        print(f"\n{'='*70}")
        print(f"PROJECT READINESS SUMMARY")
        print(f"{'='*70}")
        print(f"  UC File Found:       {'✓' if summary['uc_found'] else '✗'}")
        print(f"  Activity File Found: {'✓' if summary['activity_found'] else '✗'}")
        print(f"  Billing File Found:  {'✓' if summary['billing_found'] else '✗'}")
        print(f"  Context Files:       {summary['context_files_count']}")
        print(f"  Ready for Analysis:  {'✓ YES' if summary['ready_for_analysis'] else '✗ NO'}")
        
        if context_text:
            print(f"\n{'='*70}")
            print(f"CONTEXT TEXT PREVIEW (first 500 chars)")
            print(f"{'='*70}")
            print(context_text[:500])
            if len(context_text) > 500:
                print(f"\n... ({len(context_text) - 500:,} more characters)")
        
        print(f"\n{'='*70}")
        print(f"Source files: {', '.join(source_files) if source_files else 'None'}")
        print(f"{'='*70}\n")
        
    except Exception as e:
        logging.error(f"Error during testing: {e}")
        sys.exit(1)
