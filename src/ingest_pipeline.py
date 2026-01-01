import os
import sys
import pandas as pd
import glob
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any

# Add project root to path so we can import 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Correct imports for local execution
from src.database import DatabaseManager
from src.vector_db import FAQVectorDB
from src.config import DATA_DIR, SUPPORTED_BANKS, PRODUCT_CATEGORIES, DOCS_DIR, OPENAI_API_KEY, LLM_MODEL
from openai import OpenAI

# Setup Logging
logging.basicConfig(
    filename='ingest_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
# Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)


print(f"DEBUG: DATA_DIR from config: {DATA_DIR}")


db = DatabaseManager()
vector_db = FAQVectorDB()

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

def process_csv_files():
    """Reads all CSVs in data/ and ingests them into SQL."""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    # Filter out FAQ files from Product/SQL ingestion
    product_csvs = [f for f in csv_files if "faq" not in f.lower()]
    
    logging.info(f"Found {len(product_csvs)} Product CSV files in {DATA_DIR}")
    
    for file_path in product_csvs:
        filename = os.path.basename(file_path)
        logging.info(f"📂 Processing CSV: {filename}...")
        
        # Extract bank name from filename for column mapping
        bank_name_from_file = filename.split('_')[0].upper()
        
        try:
            from src.column_mappings import get_column_mapping
            
            df = pd.read_csv(file_path)
            
            # Get column mapping for this bank
            column_mapping = get_column_mapping(bank_name_from_file, 'product')
            reverse_mapping = {v: k for k, v in column_mapping.items()}
            
            # Preserve original column names for mapping
            original_columns = {c.strip(): c.strip() for c in df.columns}
            
            # Standardize column names (strip whitespace, lowercase)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            logging.info(f"   Columns: {list(df.columns)}")
            logging.info(f"   Using column mapping for: {bank_name_from_file}")
            
            count = 0
            for _, row in df.iterrows():
                # clean NaN values
                row = row.where(pd.notnull(row), None)
                
                # Map CSV columns to system fields using column mapping
                mapped_data = {}
                core_system_fields = ['bank_name', 'category', 'product_name', 'features', 'fees', 'interest_rate', 'eligibility']
                
                for system_field in core_system_fields:
                    # Get the CSV column name for this system field
                    csv_column = reverse_mapping.get(system_field, system_field)
                    mapped_data[system_field] = row.get(csv_column)
                
                # Check if required fields exist
                if not mapped_data.get('bank_name') or not mapped_data.get('category') or not mapped_data.get('product_name'):
                    logging.warning(f"Skipping row - Missing required fields (bank_name, category, or product_name)")
                    continue
                
                # Extract attributes (all columns NOT in the mapping)
                mapped_csv_cols = set(reverse_mapping.values())
                attributes = {}
                for col in df.columns:
                    if col not in mapped_csv_cols and row.get(col) is not None:
                        # Convert to snake_case for consistency
                        attr_key = col.lower().replace(' ', '_').replace('-', '_')
                        attributes[attr_key] = str(row[col])
                
                summary = f"{mapped_data['product_name']} is a {mapped_data['category']}."
                if mapped_data.get('features'):
                    summary += f" Features: {mapped_data['features']}."
                
                product_obj = {
                    "bank_name": mapped_data['bank_name'],
                    "category": mapped_data['category'],
                    "product_name": mapped_data['product_name'],
                    "source_type": "csv",
                    "source_file": filename,
                    "attributes": attributes,
                    "summary_text": summary
                }
                
                db.upsert_product(product_obj)
                count += 1
            logging.info(f"   Processed {count} rows from {filename}")
                
        except Exception as e:
            logging.error(f"Error processing {filename}: {e}", exc_info=True)

def extract_product_info_llm(text_content):
    """
    Uses Llama 3 to extract structured product info from text.
    """
    prompt = f"""
    You are a Banking Data Extractor. 
    Analyze the following document text and extract details about the PRIMARY financial product described.
    
    Document Text:
    {text_content[:4000]}
    
    Return a strictly valid JSON object with these keys:
    - "product_name": Exact name of the product.
    - "bank_name": One of {SUPPORTED_BANKS} or "Unknown".
    - "category": Broad category (one of {PRODUCT_CATEGORIES}).
    - "attributes": A dictionary containing key numerical/text details (fees, rates, eligibility, benefits).
    - "summary": A 1-sentence summary of the product.

    If the document describes a generic policy or multiple products without a clear primary one, return JSON with "product_name": null.

    Output ONLY JSON. No preamble.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content
        return json.loads(result)
    except Exception as e:
        logging.error(f"⚠️ Extraction Error: {e}")
        return None

def process_unstructured_docs():
    """
    Reads markdown docs, extracts product info via LLM, and creates a 'Unified Index' entry in SQL.
    """
    doc_files = glob.glob(os.path.join(DOCS_DIR, "*.md"))
    logging.info(f"Processing {len(doc_files)} Unstructured Documents...")
    
    for file_path in doc_files:
        filename = os.path.basename(file_path)
        logging.info(f"   -> Analyzing {filename}...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            extracted_data = extract_product_info_llm(content)
            
            # FIX 3: Parse bank name from filename if extraction failed
            if extracted_data and extracted_data.get("product_name"):
                # Extract bank from filename (e.g., "hdfc_*.md" -> "HDFC")
                filename_lower = filename.lower()
                detected_bank = None
                if 'hdfc' in filename_lower:
                    detected_bank = 'HDFC'
                elif 'sbi' in filename_lower:
                    detected_bank = 'SBI'
                
                # Use detected bank if LLM failed or returned Unknown/N/A
                extracted_bank = extracted_data.get('bank_name', '')
                if not extracted_bank or extracted_bank in ['Unknown', 'N/A', '']:
                    extracted_data['bank_name'] = detected_bank if detected_bank else 'Unknown'
                    logging.info(f"      Fixed bank_name: {detected_bank} (from filename)")
                
                product_obj = {
                    "bank_name": extracted_data['bank_name'],
                    "category": extracted_data['category'],
                    "product_name": extracted_data['product_name'],
                    "source_type": "extracted_doc",
                    "source_file": filename,
                    "attributes": extracted_data['attributes'],
                    "summary_text": extracted_data['summary']
                }
                db.upsert_product(product_obj)
            else:
                logging.info(f"      Skipped {filename} (No clear product found)")
        except Exception as e:
            logging.error(f"Error analyzing {filename}: {e}")

def process_faqs():
    """Reads FAQ CSVs and ingests them into Vector DB."""
    faq_files = glob.glob(os.path.join(DATA_DIR, "*_faq.csv"))
    print(f"DEBUG: Found {len(faq_files)} FAQ files in {DATA_DIR}: {faq_files}")
    logging.info(f"📚 Found {len(faq_files)} FAQ files for Vector DB ingestion.")
    
    # Reset collection to ensure clean state (optional, but good for idempotent ingestion)
    vector_db.reset_collection()
    
    for file_path in faq_files:
        filename = os.path.basename(file_path)
        logging.info(f"   Using {filename} for FAQs...")
        try:
            df = pd.read_csv(file_path)
            # Ensure keys match: bank_name, category, question, answer
            records = df.to_dict(orient='records')
            
            # Upsert to Chroma
            vector_db.upsert_faqs(records)
            logging.info(f"      Ingested {len(records)} FAQs from {filename}")
            
        except Exception as e:
            logging.error(f"❌ Error processing FAQ {filename}: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("🚀 Starting Ingestion Pipeline...")
    
    try:
        process_csv_files()
        process_unstructured_docs()
        process_faqs()

        logging.info("✅ Ingestion Complete.")
        
        # Validation
        # Log statistics for each bank
        bank_counts = {bank: db.count_products(bank_name=bank) for bank in SUPPORTED_BANKS}
        counts_str = ', '.join(f"{bank}: {count}" for bank, count in bank_counts.items())
        logging.info(f"Database Stats - {counts_str}")
        
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: {e}", exc_info=True)
