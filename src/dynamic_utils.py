"""
Dynamic Ingestion Utilities
Intelligent detection and mapping for zero-code-change configuration
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from fuzzywuzzy import fuzz
from openai import OpenAI
from src.config import OPENAI_API_KEY, LLM_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

# === STANDARD FIELD DEFINITIONS ===
STANDARD_FIELDS = {
    'bank_name': ['bank', 'bank_name', 'bankname', 'institution', 'lender', 'issuer'],
    'product_name': ['product', 'product_name', 'name', 'card_name', 'productname', 'title'],
    'category': ['category', 'type', 'product_type', 'categorytype', 'kind'],
    'fees': ['fees', 'charges', 'annual_fee', 'fee', 'cost', 'price', 'annual_charges'],
    'features': ['features', 'benefits', 'description', 'details', 'perks', 'offers'],
    'eligibility': ['eligibility', 'criteria', 'requirements', 'conditions', 'qualifying'],
    'interest_rate': ['interest', 'rate', 'apr', 'interest_rate', 'roi', 'annual_rate']
}

# === 1. BANK DETECTION ===

def detect_bank_from_filename(file_path: str) -> Optional[str]:
    """
    Extract bank name from filename pattern: bankname_products.csv
    """
    import os
    filename = os.path.basename(file_path).lower()
    
    # Common bank patterns
    common_banks = ['hdfc', 'sbi', 'icici', 'axis', 'kotak', 'indusind', 'yes', 'pnb', 'bob']
    
    for bank in common_banks:
        if bank in filename:
            return bank.upper()
    
    # Try to extract first part before underscore
    parts = filename.split('_')
    if len(parts) > 0:
        potential_bank = parts[0].replace('.csv', '').upper()
        if len(potential_bank) > 2:  # Avoid single letters
            return potential_bank
    
    return None


def detect_bank_from_content(df) -> Optional[str]:
    """
    Search for bank name keywords in DataFrame content
    """
    common_banks = ['HDFC', 'SBI', 'ICICI', 'Axis', 'Kotak', 'IndusInd', 'YES', 'PNB', 'BOB']
    
    # Search in all text columns
    for col in df.columns:
        for bank in common_banks:
            # Check if bank appears in this column
            if df[col].astype(str).str.contains(bank, case=False, na=False).any():
                return bank
    
    return None


def detect_bank_llm(df) -> str:
    """
    Use LLM to intelligently detect bank from data sample
    """
    try:
        # Get first 5 rows as sample
        sample = df.head(5).to_string(max_cols=10)
        
        prompt = f"""Analyze this banking product data and identify which bank it's from.

Data sample:
{sample}

Common banks: HDFC, SBI, ICICI, Axis, Kotak, IndusInd, YES Bank, PNB, BOB

Return ONLY the bank name (e.g., "HDFC", "SBI"). If unclear, return "Unknown"."""
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
            temperature=0.0
        )
        
        bank_name = response.choices[0].message.content.strip()
        return bank_name if bank_name != "Unknown" else None
        
    except Exception as e:
        logging.warning(f"LLM bank detection failed: {e}")
        return None


def smart_detect_bank(file_path: str, df) -> str:
    """
    Multi-strategy bank detection with fallback chain
    
    Priority:
    1. Filename pattern
    2. Content keyword search
    3. LLM analysis
    4. Default to "Unknown"
    """
    logging.info("🔍 Detecting bank...")
    
    # Try filename first (fast)
    bank = detect_bank_from_filename(file_path)
    if bank:
        logging.info(f"   ✓ Detected from filename: {bank}")
        return bank
    
    # Try content search (medium speed)
    bank = detect_bank_from_content(df)
    if bank:
        logging.info(f"   ✓ Detected from content: {bank}")
        return bank
    
    # Fallback to LLM (slower but accurate)
    bank = detect_bank_llm(df)
    if bank:
        logging.info(f"   ✓ Detected via LLM: {bank}")
        return bank
    
    logging.warning("   ⚠ Could not detect bank, using 'Unknown'")
    return "Unknown"


# === 2. COLUMN MAPPING ===

def fuzzy_map_columns(csv_columns: List[str]) -> Dict[str, str]:
    """
    Automatically map CSV columns to system fields using fuzzy matching
    
    Returns: {csv_column: system_field}
    """
    mapping = {}
    confidence_scores = {}
    
    for csv_col in csv_columns:
        csv_col_clean = csv_col.lower().strip()
        best_match = None
        best_score = 0
        best_field = None
        
        # Try to match against all standard fields
        for system_field, synonyms in STANDARD_FIELDS.items():
            for synonym in synonyms:
                score = fuzz.ratio(csv_col_clean, synonym.lower())
                
                if score > best_score:
                    best_score = score
                    best_match = synonym
                    best_field = system_field
        
        # Only map if confidence is high enough
        if best_score >= 70:  # 70% similarity threshold
            mapping[csv_col] = best_field
            confidence_scores[csv_col] = best_score
            logging.info(f"   Mapped: '{csv_col}' → '{best_field}' (confidence: {best_score}%)")
        else:
            logging.debug(f"   Skipped: '{csv_col}' (best match: {best_match} at {best_score}%)")
    
    return mapping


def llm_map_columns(csv_columns: List[str]) -> Dict[str, str]:
    """
    Use LLM to intelligently map columns when fuzzy matching fails
    """
    try:
        columns_str = ", ".join(csv_columns)
        
        prompt = f"""Map these CSV columns to standard banking product fields.

CSV Columns: {columns_str}

Standard Fields: bank_name, product_name, category, fees, features, eligibility, interest_rate

Return a JSON object mapping CSV columns to standard fields. Only map columns that clearly match.
Example: {{"Annual Fee": "fees", "Card Name": "product_name"}}

Return ONLY the JSON, no explanations."""
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        mapping = json.loads(response.choices[0].message.content)
        return mapping
        
    except Exception as e:
        logging.warning(f"LLM column mapping failed: {e}")
        return {}


def smart_map_columns(csv_columns: List[str]) -> Tuple[Dict[str, str], float]:
    """
    Intelligent column mapping with fallback strategy
    
    Returns: (mapping_dict, confidence_score)
    """
    logging.info("🗺️  Mapping columns...")
    
    # Try fuzzy matching first
    fuzzy_mapping = fuzzy_map_columns(csv_columns)
    
    # Calculate confidence based on how many critical fields were mapped
    critical_fields = ['product_name', 'bank_name', 'category']
    mapped_critical = sum(1 for field in critical_fields if field in fuzzy_mapping.values())
    confidence = mapped_critical / len(critical_fields)
    
    # If confidence is low, use LLM fallback
    if confidence < 0.67:  # Less than 2/3 critical fields mapped
        logging.info("   Low confidence, trying LLM fallback...")
        llm_mapping = llm_map_columns(csv_columns)
        
        # Merge mappings (LLM takes precedence for conflicts)
        fuzzy_mapping.update(llm_mapping)
        
        # Recalculate confidence
        mapped_critical = sum(1 for field in critical_fields if field in fuzzy_mapping.values())
        confidence = mapped_critical / len(critical_fields)
    
    logging.info(f"   Mapping confidence: {confidence*100:.0f}%")
    return fuzzy_mapping, confidence


# === 3. HANDLE EXTRA COLUMNS (100+ columns) ===

def extract_product_with_unlimited_columns(row, column_mapping: Dict, bank_name: str) -> Dict:
    """
    Extract product data with dynamic JSON storage for unmapped columns
    """
    # Reverse mapping: system_field -> csv_column
    reverse_mapping = {v: k for k, v in column_mapping.items()}
    
    # Extract core fields
    core_data = {
        'bank_name': row.get(reverse_mapping.get('bank_name')) or bank_name,
        'product_name': row.get(reverse_mapping.get('product_name')),
        'category': row.get(reverse_mapping.get('category')),
    }
    
    # Build attributes JSON for everything else
    attributes = {}
    
    # Add known fields
    for field in ['fees', 'features', 'interest_rate', 'eligibility']:
        csv_col = reverse_mapping.get(field)
        if csv_col and csv_col in row.index:
            value = row.get(csv_col)
            if value  is not None and str(value).strip():
                attributes[field] = str(value)
    
    # Add all unmapped columns as additional attributes
    mapped_csv_cols = set(column_mapping.keys())
    for col in row.index:
        if col not in mapped_csv_cols:
            value = row.get(col)
            if value is not None and str(value).strip() and str(value) != 'nan':
                # Clean column name for JSON key
                clean_key = col.lower().replace(' ', '_').replace('-', '_')
                attributes[clean_key] = str(value)
    
    core_data['attributes'] = attributes
    core_data['summary_text'] = f"{core_data['product_name']} is a {core_data['category']} from {core_data['bank_name']}."
    core_data['source_type'] = 'csv_dynamic'
    
    return core_data


# === 4. EDGE CASES ===

def infer_headers_llm(first_row: List) -> List[str]:
    """
    Edge Case: CSV has no headers - use LLM to infer
    """
    try:
        row_str = ", ".join([str(v) for v in first_row[:10]])  # First 10 values
        
        prompt = f"""This is the first row of a banking products CSV file with missing headers.
Infer appropriate column names.

First row values: {row_str}

Return a JSON array of inferred column names.
Example: ["bank_name", "product_name", "category", "fees", ...]"""
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get('headers', [f'column_{i}' for i in range(len(first_row))])
        
    except:
        # Fallback to generic names
        return [f'column_{i}' for i in range(len(first_row))]


def detect_file_format(file_path: str) -> str:
    """
    Edge Case: Detect file format (CSV, Excel, JSON)
    """
    ext = file_path.lower().split('.')[-1]
    return ext


# === EXPORT ===
__all__ = [
    'smart_detect_bank',
    'smart_map_columns', 
    'extract_product_with_unlimited_columns',
    'infer_headers_llm',
    'detect_file_format'
]
