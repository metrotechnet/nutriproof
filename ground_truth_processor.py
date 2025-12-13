#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ground Truth OCR Processing Script

This script processes all PDF documents in D:/Nutriss/ground_truth project folders,
performs OCR extraction, and updates the Temps and Visite fields in table_page_xx.json files.

Usage:
    python ground_truth_processor.py

Requirements:
    - All dependencies from the main app (Flask, Google Cloud, etc.)
    - PDF files in project folders under D:/Nutriss/ground_truth
"""

import os
import json
import glob
import sys
from datetime import datetime

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py.extract_tables import OCRDocument
from py.gstorage import GSStorage
from py.config import get_project_id, get_location, get_ocr_processor_id

# Configuration
GROUND_TRUTH_ROOT = r"D:\Nutriss\ground_truth"
CONFIG_PATH = "dbase/bilan_lipidique.json"
LOCAL_TEMP_FOLDER = "temp_processing"
GCS_FOLDER = "nutriss-dbase-dev"  # Use dev for ground truth processing

class GroundTruthProcessor:
    def __init__(self):
        # Initialize storage and OCR components
        self.gcs = GSStorage(LOCAL_TEMP_FOLDER, GCS_FOLDER)
        self.ocr_document = OCRDocument(self.gcs)
        
        # Load configuration
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # Create temp folder
        os.makedirs(LOCAL_TEMP_FOLDER, exist_ok=True)
        
        print(f"Ground Truth Processor initialized")
        print(f"Root folder: {GROUND_TRUTH_ROOT}")
        print(f"Config loaded with {len(self.config)} parameters")

    def find_all_projects(self):
        """Find all project folders in the ground truth directory."""
        if not os.path.exists(GROUND_TRUTH_ROOT):
            print(f"Error: Ground truth directory not found: {GROUND_TRUTH_ROOT}")
            return []
        
        projects = []
        for item in os.listdir(GROUND_TRUTH_ROOT):
            project_path = os.path.join(GROUND_TRUTH_ROOT, item)
            if os.path.isdir(project_path):
                # Look for PDF files in the project
                pdf_files = glob.glob(os.path.join(project_path, "*.pdf"))
                if pdf_files:
                    projects.append({
                        'name': item,
                        'path': project_path,
                        'pdf_files': pdf_files
                    })
        
        print(f"Found {len(projects)} projects with PDF files")
        return projects

    def process_pdf_document(self, pdf_path, output_dir):
        """Process a single PDF document and extract OCR data."""
        try:
            # Get number of pages
            nbr_pages = self.ocr_document.get_pdf_page_count(pdf_path)
            print(f"  Processing {nbr_pages} pages...")
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            results = []
            
            # Process each page
            for page_idx in range(nbr_pages):
                print(f"    Processing page {page_idx + 1}/{nbr_pages}...")
                
                try:
                    # Extract page as image
                    chunk_file = self.ocr_document.get_pdf_image(
                        pdf_path, output_dir, 
                        page_index=page_idx, 
                        dpi=300
                    )
                    
                    # Get page ID
                    pageid = os.path.splitext(os.path.basename(chunk_file))[0]
                    
                    # Get document layout using OCR
                    layout = self.ocr_document.get_document_layout(
                        chunk_file, mime_type="image/png"
                    )
                    
                    # Save layout to JSON
                    layout_json_path = os.path.join(output_dir, f"output_{pageid}.json")
                    with open(layout_json_path, "w", encoding="utf-8") as f:
                        json.dump(layout, f, indent=4, ensure_ascii=False)
                    
                    # Extract tables using the main extraction method
                    extraction_result = self.ocr_document.extract_tables(
                        CONFIG_PATH, layout_json_path, output_dir, pageid
                    )
                    
                    # Check if we have a valid table file
                    table_file = os.path.join(output_dir, f"table_{pageid}.json")
                    if os.path.exists(table_file):
                        results.append({
                            'page': page_idx + 1,
                            'pageid': pageid,
                            'table_file': table_file,
                            'extraction_result': extraction_result
                        })
                        print(f"    [OK] Page {page_idx + 1} processed successfully")
                    else:
                        print(f"    [WARNING] Page {page_idx + 1} - no table data extracted")
                        
                except Exception as e:
                    print(f"    [ERROR] Error processing page {page_idx + 1}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"  Error processing PDF {pdf_path}: {str(e)}")
            return []

    def update_temps_visite_fields(self, table_file_path):
        """Update Temps and Visite fields in a table JSON file."""
        try:
            if not os.path.exists(table_file_path):
                return False
            
            # Load existing table data
            with open(table_file_path, 'r', encoding='utf-8') as f:
                table_data = json.load(f)
            
            # Check if Temps and Visite need updating
            temps_updated = False
            visite_updated = False
            
            if 'Temps' in table_data and table_data['Temps'] is not None:
                print(f"      Found Temps: {table_data['Temps']}")
                temps_updated = True
            
            if 'Visite' in table_data and table_data['Visite'] is not None:
                print(f"      Found Visite: {table_data['Visite']}")
                visite_updated = True
            
            return temps_updated or visite_updated
            
        except Exception as e:
            print(f"      Error updating fields in {table_file_path}: {str(e)}")
            return False

    
    def process_project(self, project):
        """Process all PDF files in a project."""
        print(f"\n[PROJECT] Processing project: {project['name']}")
        
        project_results = {
            'project_name': project['name'],
            'project_path': project['path'],
            'processed_files': [],
            'errors': []
        }
        
        for pdf_file in project['pdf_files']:
            print(f"\n[PDF] Processing PDF: {os.path.basename(pdf_file)}")
            
            # Create output directory for this PDF
            pdf_name = os.path.splitext(os.path.basename(pdf_file))[0]
            output_dir = os.path.join(project['path'], f"ocr_output_{pdf_name}")
            
            try:
                # Process the PDF
                page_results = self.process_pdf_document(pdf_file, output_dir)
                
                if page_results:
                    
                    # Update Temps and Visite fields for each page
                    updated_pages = []
                    for page_result in page_results:
                        print(f"    [UPDATE] Updating fields for page {page_result['page']}...")
                        if self.update_temps_visite_fields(page_result['table_file']):
                            updated_pages.append(page_result['page'])
                    
                    project_results['processed_files'].append({
                        'pdf_file': pdf_file,
                        'output_dir': output_dir,
                        'total_pages': len(page_results),
                        'updated_pages': updated_pages
                    })
                    
                    print(f"    [COMPLETE] Completed {os.path.basename(pdf_file)} - {len(page_results)} pages processed")
                else:
                    print(f"    [ERROR] No pages processed for {os.path.basename(pdf_file)}")
                    
            except Exception as e:
                error_msg = f"Error processing {pdf_file}: {str(e)}"
                print(f"    [ERROR] {error_msg}")
                project_results['errors'].append(error_msg)
        
        return project_results

    def run_full_processing(self):
        """Run the complete ground truth processing pipeline."""
        print("Starting Ground Truth OCR Processing")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Find all projects
        projects = self.find_all_projects()
        if not projects:
            print("No projects found to process!")
            return
        
        # Process each project
        all_results = []
        for i, project in enumerate(projects, 1):
            print(f"\n[{i}/{len(projects)}] " + "="*40)
            project_result = self.process_project(project)
            all_results.append(project_result)
        
        # Generate summary report
        self.generate_summary_report(all_results, start_time)

    def generate_summary_report(self, results, start_time):
        """Generate a summary report of the processing."""
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print("PROCESSING SUMMARY REPORT")
        print("="*60)
        
        total_projects = len(results)
        total_files = sum(len(r['processed_files']) for r in results)
        total_pages = sum(sum(f['total_pages'] for f in r['processed_files']) for r in results)
        total_errors = sum(len(r['errors']) for r in results)
        
        print(f"Processing Time: {duration}")
        print(f"Projects Processed: {total_projects}")
        print(f"PDF Files Processed: {total_files}")
        print(f"Total Pages Processed: {total_pages}")
        print(f"Total Errors: {total_errors}")
        
        print("\nProject Details:")
        for result in results:
            print(f"\n  Project: {result['project_name']}")
            print(f"     Files: {len(result['processed_files'])}")
            print(f"     Pages: {sum(f['total_pages'] for f in result['processed_files'])}")
            print(f"     Errors: {len(result['errors'])}")
            
            if result['errors']:
                print("     Error List:")
                for error in result['errors'][:3]:  # Show first 3 errors
                    print(f"        - {error}")
                if len(result['errors']) > 3:
                    print(f"        ... and {len(result['errors']) - 3} more")
        
        # Save detailed report
        report_file = os.path.join(GROUND_TRUTH_ROOT, f"processing_report_{start_time.strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'processing_info': {
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'duration_seconds': duration.total_seconds(),
                        'total_projects': total_projects,
                        'total_files': total_files,
                        'total_pages': total_pages,
                        'total_errors': total_errors
                    },
                    'detailed_results': results
                }, f, indent=2, ensure_ascii=False)
            print(f"\nDetailed report saved to: {report_file}")
        except Exception as e:
            print(f"\nCould not save report: {str(e)}")

def main():
    """Main function to run the ground truth processor."""
    try:
        processor = GroundTruthProcessor()
        processor.run_full_processing()
    except KeyboardInterrupt:
        print("\n\nProcessing interrupted by user")
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()