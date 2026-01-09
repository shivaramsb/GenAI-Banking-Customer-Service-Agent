"""
Dynamic FAQ utilities for intelligent column mapping and extra fields handling
"""

import logging
from typing import Dict, List, Tuple
from fuzzywuzzy import fuzz

# Standard FAQ field mappings
FAQ_STANDARD_FIELDS = {
    'bank_name': ['bank', 'bank_name', 'bankname', 'institution'],
    'category': ['category', 'type', 'topic', 'subject'],
    'question': ['question', 'q', 'query', 'ask'],
    'answer': ['answer', 'a', 'response', 'reply', 'solution']
}


def fuzzy_map_faq_columns(csv_columns: List[str]) -> Tuple[Dict[str, str], float]:
    """
    Automatically map FAQ CSV columns to standard fields
    
    Returns: (mapping_dict, confidence_score)
    """
    mapping = {}
    
    for csv_col in csv_columns:
        csv_col_clean = csv_col.lower().strip()
        best_match = None
        best_score = 0
        best_field = None
        
        # Try to match against all standard fields
        for system_field, synonyms in FAQ_STANDARD_FIELDS.items():
            for synonym in synonyms:
                score = fuzz.ratio(csv_col_clean, synonym.lower())
                
                if score > best_score:
                    best_score = score
                    best_match = synonym
                    best_field = system_field
        
        # Only map if confidence is high enough
        if best_score >= 70:  # 70% similarity threshold
            mapping[csv_col] = best_field
            logging.info(f"   FAQ Mapped: '{csv_col}' → '{best_field}' (confidence: {best_score}%)")
    
    # Calculate confidence based on critical fields
    critical_fields = ['question', 'answer']
    mapped_critical = sum(1 for field in critical_fields if field in mapping.values())
    confidence = mapped_critical / len(critical_fields)
    
    return mapping, confidence


def extract_faq_with_extra_columns(row, column_mapping: Dict) -> Dict:
    """
    Extract FAQ data with support for unlimited extra columns
    
    Required: question, answer
    Optional: bank_name, category
    Extra: Any other columns stored in metadata
    """
    # Reverse mapping: system_field -> csv_column
    reverse_mapping = {v: k for k, v in column_mapping.items()}
    
    # Extract core fields
    faq_data = {
        'question': row.get(reverse_mapping.get('question', 'question')),
        'answer': row.get(reverse_mapping.get('answer', 'answer')),
        'bank_name': row.get(reverse_mapping.get('bank_name', 'bank_name'), 'Unknown'),
        'category': row.get(reverse_mapping.get('category', 'category'), 'General'),
    }
    
    # Add all unmapped columns as extra metadata
    mapped_csv_cols = set(column_mapping.keys())
    extra_metadata = {}
    
    for col in row.index:
        if col not in mapped_csv_cols:
            value = row.get(col)
            if value is not None and str(value).strip() and str(value) != 'nan':
                # Clean column name for metadata key
                clean_key = col.lower().replace(' ', '_').replace('-', '_')
                extra_metadata[clean_key] = str(value)
    
    # Store extra fields in a special metadata key
    if extra_metadata:
        faq_data['extra_fields'] = extra_metadata
    
    return faq_data


__all__ = [
    'fuzzy_map_faq_columns',
    'extract_faq_with_extra_columns'
]
