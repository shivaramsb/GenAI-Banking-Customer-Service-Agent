"""
Column Mapping Configuration
Define how your CSV columns map to system fields
"""

# Default mapping (current system)
DEFAULT_COLUMN_MAPPING = {
    'bank_name': 'bank_name',
    'category': 'category', 
    'product_name': 'product_name',
    'features': 'features',
    'fees': 'fees',
    'interest_rate': 'interest_rate',
    'eligibility': 'eligibility'
}

# Example: If your CSV has different column names
CUSTOM_COLUMN_MAPPINGS = {
    # Example 1: Your bank uses different naming
    'ICICI': {
        'Bank': 'bank_name',           
        'Type': 'category',            
        'Name': 'product_name',        
        'Benefits': 'features',        
        'Annual Fee': 'fees',          
        'Rate': 'interest_rate',       
        'Requirements': 'eligibility'  
    },
    
    # Example 2: Another bank with completely different schema
    'Axis': {
        'bank': 'bank_name',
        'product_type': 'category',
        'product': 'product_name',
        'description': 'features',
        'charges': 'fees',
        'apr': 'interest_rate',
        'criteria': 'eligibility'
    }
}

# FAQ Column Mapping
DEFAULT_FAQ_MAPPING = {
    'bank_name': 'bank_name',
    'category': 'category',
    'question': 'question',
    'answer': 'answer'
}

CUSTOM_FAQ_MAPPINGS = {
    # Example: Your FAQ CSV has different columns
    'ICICI': {
        'Bank': 'bank_name',
        'Topic': 'category',
        'Q': 'question',
        'A': 'answer'
    }
}

def get_column_mapping(bank_name, mapping_type='product'):
    """
    Get column mapping for a specific bank
    
    Args:
        bank_name: Name of the bank (e.g., 'ICICI', 'Axis')
        mapping_type: 'product' or 'faq'
    
    Returns:
        Dictionary mapping CSV columns to system fields
    """
    if mapping_type == 'product':
        return CUSTOM_COLUMN_MAPPINGS.get(bank_name.upper(), DEFAULT_COLUMN_MAPPING)
    else:
        return CUSTOM_FAQ_MAPPINGS.get(bank_name.upper(), DEFAULT_FAQ_MAPPING)
