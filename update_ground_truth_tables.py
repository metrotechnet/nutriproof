#!/usr/bin/env python3
"""
Ground Truth Table Updater Script

This script updates existing table_page_xx.json files in ground truth folders
by reprocessing only the Temps and Visite fields using the existing OCR data.

Usage:
    python update_ground_truth_tables.py

This is useful when you already have OCR output but want to update specific fields.
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

# Configuration
GROUND_TRUTH_ROOT = r"D:\Nutriss\ground_truth"
CONFIG_PATH = "dbase/bilan_lipidique.json"
LOCAL_TEMP_FOLDER = "temp_update"
GCS_FOLDER = "nutriss-dbase-dev"

class GroundTruthTableUpdater:
    def __init__(self):
        # Initialize storage and OCR components
        self.gcs = GSStorage(LOCAL_TEMP_FOLDER, GCS_FOLDER)
        self.ocr_document = OCRDocument(self.gcs)
        
        # Create temp folder
        os.makedirs(LOCAL_TEMP_FOLDER, exist_ok=True)
        
        print("Ground Truth Table Updater initialized")

    def find_existing_table_files(self):
        """Find all existing table_page_xx.json files in ground truth folders."""
        table_files = []
        
        if not os.path.exists(GROUND_TRUTH_ROOT):
            print(f"Error: Ground truth directory not found: {GROUND_TRUTH_ROOT}")
            return []
        
        # Search for table files in all subdirectories
        pattern = os.path.join(GROUND_TRUTH_ROOT, "**", "table_page_*.json")
        found_files = glob.glob(pattern, recursive=True)
        
        for file_path in found_files:
            # Also look for corresponding output files
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            
            # Extract page info from filename (e.g., table_page_1.json -> page_1)
            if base_name.startswith("table_page_") and base_name.endswith(".json"):
                page_id = base_name[11:-5]  # Remove "table_page_" and ".json"
                output_file = os.path.join(dir_name, f"output_page_{page_id}.json")
                
                table_files.append({
                    'table_file': file_path,
                    'output_file': output_file if os.path.exists(output_file) else None,
                    'page_id': page_id,
                    'project_dir': dir_name
                })
        
        print(f"Found {len(table_files)} existing table files")
        return table_files

    def update_table_file(self, table_info):
        """Update Temps and Visite fields in a specific table file."""
        table_file = table_info['table_file']
        output_file = table_info['output_file']
        page_id = table_info['page_id']
        
        print(f"  📄 Updating table for page {page_id}...")
        
        try:
            # Look for ocr_output subfolder to find the output file
            base_dir = os.path.dirname(table_file)
            ocr_output_dir = None
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path) and item.startswith("ocr_output"):
                    ocr_output_dir = item_path
                    break
            
            if not ocr_output_dir:
                print(f"    ⚠ No ocr_output subfolder found for page {page_id}")
                return False
            
            # Look for output file in ocr_output folder
            ocr_output_file = os.path.join(ocr_output_dir, f"table_page_{page_id}.json")
            if not os.path.exists(ocr_output_file):
                print(f"    ⚠ No OCR output file found in ocr_output folder for page {page_id}")
                return False
            
            # Load OCR data from ocr_output folder
            with open(ocr_output_file, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            # Load existing table data
            with open(table_file, 'r', encoding='utf-8') as f:
                table_data = json.load(f)
            
            # Extract Temps and Visite using the existing extraction method
            print(f"    🔍 Extracting Temps and Visite fields...")
            
            # Process Temps field
            table_data['Temps'] = ocr_data['Temps']
            
            # Process Visite field
            table_data['Visite'] = ocr_data['Visite']

            # Save updated table data to a new output folder with flattened structure
            # Extract project name from the path
            path_parts = table_file.split(os.sep)
            ground_truth_idx = None
            for i, part in enumerate(path_parts):
                if part == "ground_truth":
                    ground_truth_idx = i
                    break
            
            if ground_truth_idx is not None and ground_truth_idx + 1 < len(path_parts):
                project_name = path_parts[ground_truth_idx + 1]
                output_dir = os.path.join(GROUND_TRUTH_ROOT, "updated_tables", project_name)
                os.makedirs(output_dir, exist_ok=True)
                
                # Save with just the filename in the project folder
                filename = os.path.basename(table_file)
                output_file_path = os.path.join(output_dir, filename)
                
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(table_data, f, indent=2, ensure_ascii=False)
                
                print(f"    ✅ Table file updated and saved to: {output_file_path}")
                
                # Also copy corresponding bbox files
                self.copy_bbox_files(table_info, project_name, output_dir)
                
            else:
                print(f"    ❌ Could not determine project name from path: {table_file}")
                return False
            return True
            
        except Exception as e:
            print(f"    ❌ Error updating table file: {str(e)}")
            return False

    def copy_bbox_files(self, table_info, project_name, output_dir):
        """Copy corresponding label_bbox and value_bbox files to the updated_tables folder."""
        try:
            # Get the directory where the table file is located
            base_dir = os.path.dirname(table_info['table_file'])
            page_id = table_info['page_id']
            
            # Look for ocr_output subfolder
            ocr_output_dir = None
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path) and item.startswith("ocr_output"):
                    ocr_output_dir = item_path
                    break
            
            if not ocr_output_dir:
                print(f"    ⚠ No ocr_output subfolder found in {base_dir}")
                return
            
            # Find and copy label_bbox file
            label_bbox_file = os.path.join(ocr_output_dir, f"label_bbox_page_{page_id}.json")
            if os.path.exists(label_bbox_file):
                dest_label_file = os.path.join(output_dir, f"label_bbox_page_{page_id}.json")
                with open(label_bbox_file, 'r', encoding='utf-8') as src:
                    label_data = json.load(src)
                with open(dest_label_file, 'w', encoding='utf-8') as dest:
                    json.dump(label_data, dest, indent=2, ensure_ascii=False)
                print(f"    📋 Copied label_bbox_page_{page_id}.json")
            else:
                print(f"    ⚠ label_bbox_page_{page_id}.json not found in {ocr_output_dir}")
            
            # Find and copy value_bbox file
            value_bbox_file = os.path.join(ocr_output_dir, f"value_bbox_page_{page_id}.json")
            if os.path.exists(value_bbox_file):
                dest_value_file = os.path.join(output_dir, f"value_bbox_page_{page_id}.json")
                with open(value_bbox_file, 'r', encoding='utf-8') as src:
                    value_data = json.load(src)
                with open(dest_value_file, 'w', encoding='utf-8') as dest:
                    json.dump(value_data, dest, indent=2, ensure_ascii=False)
                print(f"    📋 Copied value_bbox_page_{page_id}.json")
            else:
                print(f"    ⚠ value_bbox_page_{page_id}.json not found in {ocr_output_dir}")

        except Exception as e:
            print(f"    ❌ Error copying bbox files: {str(e)}")

    def update_all_tables(self):
        """Update all found table files and save to a flattened output folder structure."""
        print("🚀 Starting Ground Truth Table Update")
        print("=" * 50)
        print(f"📁 Output folder: {os.path.join(GROUND_TRUTH_ROOT, 'updated_tables')}")
        print("📝 Files will be saved as: updated_tables/project_name/table_page_xx.json")
        print("� Bbox files will be copied: updated_tables/project_name/label_bbox_page_xx.json")
        print("📋 Bbox files will be copied: updated_tables/project_name/value_bbox_page_xx.json")
        print("�📝 Original files will be preserved")
        print()
        
        start_time = datetime.now()
        
        # Find all table files
        table_files = self.find_existing_table_files()
        if not table_files:
            print("No table files found to update!")
            return
        
        # Group by project directory
        projects = {}
        for table_info in table_files:
            project_dir = table_info['project_dir']
            project_name = os.path.basename(project_dir)
            
            # Skip projects starting with ocr_output
            if project_name.startswith("ocr_output"):
                continue
            
            # Skip projects in updated_tables folder
            if "updated_tables" in project_dir:
                continue
                 
            if project_dir not in projects:
                projects[project_dir] = []
            projects[project_dir].append(table_info)
        
        # Process each project
        total_updated = 0
        total_failed = 0
        
        for i, (project_dir, table_list) in enumerate(projects.items(), 1):
            project_name = os.path.basename(project_dir)
            print(f"\n[{i}/{len(projects)}] 📁 Project: {project_name}")
            print(f"    📄 Files to update: {len(table_list)}")
            
            project_updated = 0
            for table_info in table_list:
                if self.update_table_file(table_info):
                    project_updated += 1
                    total_updated += 1
                else:
                    total_failed += 1
            
            print(f"    ✅ Updated: {project_updated}/{len(table_list)} files")
        
        # Summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "="*50)
        print("📊 UPDATE SUMMARY")
        print("="*50)
        print(f"⏱️  Total Time: {duration}")
        print(f"📁 Projects Processed: {len(projects)}")
        print(f"📄 Files Found: {len(table_files)}")
        print(f"✅ Successfully Updated: {total_updated}")
        print(f"❌ Failed Updates: {total_failed}")
        print(f"📊 Success Rate: {(total_updated/len(table_files)*100):.1f}%")

def main():
    """Main function to run the table updater."""
    try:
        updater = GroundTruthTableUpdater()
        updater.update_all_tables()
    except KeyboardInterrupt:
        print("\n\n⚠️  Update interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()