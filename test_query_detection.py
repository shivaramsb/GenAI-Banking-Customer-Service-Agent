"""
Test script to verify query detection logic catches all comprehensive queries
"""

from src.config import SUPPORTED_BANKS

def test_query_detection(query):
    """Test if a query should be classified as comprehensive"""
    query_lower = query.lower().strip()
    
    # Explicit listing phrases
    explicit_list_phrases = [
        'all', 'list all', 'explain all', 'list of', 'show me all',
        'what are the', 'what are all', 'which', 'show me',
        'give me', 'tell me about'
    ]
    
    # Product category keywords
    product_keywords = [
        'credit card', 'debit card', 'loan', 'account', 
        'cards', 'loans', 'products'
    ]
    
    has_explicit_phrase = any(phrase in query_lower for phrase in explicit_list_phrases)
    has_product_plural = any(keyword in query_lower for keyword in product_keywords)
    has_bank_name = any(bank.lower() in query_lower for bank in SUPPORTED_BANKS)
    
    is_comprehensive = has_explicit_phrase or (has_bank_name and has_product_plural)
    max_results = 50 if is_comprehensive else 15
    
    return is_comprehensive, max_results


# Test all user's queries
test_queries = [
    "hdfc credit cards",
    "what are the credit cards hdfc offers",
    "list of all hdfc credit cards",
    "show me hdfc credit cards",
    "which hdfc credit cards are available",
    "what are the hdfc cards"
]

print("Query Detection Test Results:")
print("=" * 80)

for query in test_queries:
    is_comp, max_res = test_query_detection(query)
    status = "✅ PASS" if max_res == 50 else "❌ FAIL"
    print(f"{status} | max_results={max_res:2d} | {query}")

print("=" * 80)
print("\nExpected: All queries should show max_results=50 (comprehensive)")
