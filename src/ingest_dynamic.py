"""
Enhanced Dynamic Ingestion Pipeline
Zero-code-change ingestion supporting any bank/format/structure
"""

import os
import sys
import pandas as pd
import glob
import logging
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager
from src.vector_db import FAQVectorDB
from src.config import PRODUCTS_DIR, FAQS_DIR, OPENAI_API_KEY, LLM_MODEL
from src.dynamic_utils import (
    smart_detect_bank,
    smart_map_columns,
    extract_product_with_unlimited_columns,
    infer_headers_llm,
    detect_file_format
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ingest_dynamic.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

db = DatabaseManager()
vector_db = FAQVectorDB()


def process_csv_dynamic(file_path: str):
    """
    Process CSV with intelligent detection and mapping
    Handles any column structure, any bank name
    """
    filename = os.path.basename(file_path)
    logging.info(f"\n{'='*80}")
    logging.info(f"📄 Processing: {filename}")
    logging.info(f"{'='*80}")
    
    try:
        # Load CSV
        df = pd.read_csv(file_path)
        
        # Edge Case: No headers detected
        if df.columns[0].startswith('Unnamed') or pd.isna(df.columns[0]):
            logging.warning("⚠️  No headers detected, inferring from first row...")
            first_row = df.iloc[0].tolist()
            inferred_headers = infer_headers_llm(first_row)
            df.columns = inferred_headers
            df = df[1:]  # Skip the first row (was used for inference)
        
        logging.info(f"📊 Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Step 1: Detect bank
        bank_name = smart_detect_bank(file_path, df)
        
        # Step 2: Map columns
        column_mapping, confidence = smart_map_columns(df.columns.tolist())
        
        if confidence < 0.33:  # Less than 1/3 critical fields
            logging.error(f"❌ Mapping confidence too low ({confidence*100:.0f}%), skipping file")
            logging.error(f"   Detected mapping: {column_mapping}")
            return 0
        
        # Step 3: Process rows
        count = 0
        skipped = 0
        
        for _, row in df.iterrows():
            # Clean NaN values
            row = row.where(pd.notnull(row), None)
            
            try:
                # Extract with dynamic column handling
                product_obj = extract_product_with_unlimited_columns(row, column_mapping, bank_name)
                
                # Validate critical fields
                if not product_obj.get('product_name') or not product_obj.get('category'):
                    skipped += 1
                    continue
                
                # Add source metadata
                product_obj['source_file'] = filename
                
                # Upsert to database
                db.upsert_product(product_obj)
                count += 1
                
            except Exception as e:
                logging.warning(f"   ⚠️  Skipped row: {e}")
                skipped += 1
                continue
        
        logging.info(f"✅ Processed {count} products ({skipped} skipped)")
        return count
        
    except Exception as e:
        logging.error(f"❌ Error processing {filename}: {e}", exc_info=True)
        return 0


def process_excel_dynamic(file_path: str):
    """
    Process Excel files (multi-sheet support)
    """
    filename = os.path.basename(file_path)
    logging.info(f"\n📗 Processing Excel: {filename}")
    
    try:
        xls = pd.ExcelFile(file_path)
        total_count = 0
        
        for sheet_name in xls.sheet_names:
            logging.info(f"  📑 Sheet: {sheet_name}")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Treat each sheet as separate CSV
            # Save temporarily and process
            temp_csv = f"temp_{sheet_name}.csv"
            df.to_csv(temp_csv, index=False)
            count = process_csv_dynamic(temp_csv)
            os.remove(temp_csv)
            
            total_count += count
        
        logging.info(f"✅ Total from Excel: {total_count} products")
        return total_count
        
    except Exception as e:
        logging.error(f"❌ Error processing Excel {filename}: {e}")
        return 0


def process_json_dynamic(file_path: str):
    """
    Process JSON files with product data
    """
    filename = os.path.basename(file_path)
    logging.info(f"\n📋 Processing JSON: {filename}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Check if it's a dict of products
            if 'products' in data:
                df = pd.DataFrame(data['products'])
            else:
                # Assume dict is a single product
                df = pd.DataFrame([data])
        else:
            logging.error(f"❌ Unsupported JSON structure")
            return 0
        
        # Save as temp CSV and process
        temp_csv = f"temp_json.csv"
        df.to_csv(temp_csv, index=False)
        count = process_csv_dynamic(temp_csv)
        os.remove(temp_csv)
        
        logging.info(f"✅ Processed {count} products from JSON")
        return count
        
    except Exception as e:
        logging.error(f"❌ Error processing JSON {filename}: {e}")
        return 0


def process_all_files():
    """
    Main ingestion - processes ALL supported file formats
    """
    logging.info("\n" + "="*80)
    logging.info("🚀 DYNAMIC INGESTION PIPELINE")
    logging.info("="*80)
    
    # Find all supported files in products folder
    all_files = []
    for ext in ['*.csv', '*.xlsx', '*.xls', '*.json']:
        files = glob.glob(os.path.join(PRODUCTS_DIR, ext))
        all_files.extend(files)
    
    logging.info(f"\n📂 Found {len(all_files)} product files")
    
    total_products = 0
    
    for file_path in all_files:
        file_format = detect_file_format(file_path)
        
        if file_format in ['csv']:
            count = process_csv_dynamic(file_path)
        elif file_format in ['xlsx', 'xls']:
            count = process_excel_dynamic(file_path)
        elif file_format in ['json']:
            count = process_json_dynamic(file_path)
        else:
            logging.warning(f"⚠️  Unsupported format: {file_format}")
            continue
        
        total_products += count
    
    logging.info(f"\n{'='*80}")
    logging.info(f"✅ INGESTION COMPLETE: {total_products} total products")
    logging.info(f"{'='*80}\n")
    
    return total_products


def process_faqs_dynamic():
    """
    Process FAQ files from organized faqs folder
    """
    faq_files = glob.glob(os.path.join(FAQS_DIR, "*.csv"))
    logging.info(f"\n📚 Processing {len(faq_files)} FAQ files...")
    
    vector_db.reset_collection()
    
    for file_path in faq_files:
        filename = os.path.basename(file_path)
        try:
            df = pd.read_csv(file_path)
            records = df.to_dict(orient='records')
            vector_db.upsert_faqs(records)
            logging.info(f"  ✅ {filename}: {len(records)} FAQs")
        except Exception as e:
            logging.error(f"  ❌ {filename}: {e}")
    
    logging.info("✅ FAQ ingestion complete\n")


if __name__ == "__main__":
    logging.info("Starting Dynamic Ingestion Pipeline...")
    
    try:
        # Process products
        total = process_all_files()
        
        # Process FAQs
        process_faqs_dynamic()
        
        # Summary
        logging.info(f"\n📊 FINAL SUMMARY:")
        logging.info(f"   Total products ingested: {total}")
        
        # Show banks detected
        result = db.execute_raw_query("SELECT DISTINCT bank_name FROM products ORDER BY bank_name")
        banks = [r['bank_name'] for r in result]
        logging.info(f"   Banks in database: {', '.join(banks)}")
        
        # Show categories detected
        result = db.execute_raw_query("SELECT DISTINCT category FROM products ORDER BY category")
        categories = [r['category'] for r in result]
        logging.info(f"   Categories in database: {', '.join(categories)}")
        
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: {e}", exc_info=True)
