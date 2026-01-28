"""
Query Relevance Validator (Zero-Hardcoding Solution)

Uses LLM to detect if a query is banking-related, with caching for performance.
Part of the zero-hardcoding initiative to remove all keyword lists.
"""

import logging
from functools import lru_cache
from openai import OpenAI
from src.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

@lru_cache(maxsize=500)  # Cache 500 recent queries (memory: ~50KB)
def is_banking_query(query: str) -> bool:
    """
    Determine if a user query is related to banking/finance.
    
    Uses GPT-4o-mini with aggressive caching to minimize cost and latency.
    
    Args:
        query: User's input query
        
    Returns:
        True if query is banking-related, False otherwise
        
    Examples:
        >>> is_banking_query("SBI debit cards")
        True
        >>> is_banking_query("shivaram")
        False
        >>> is_banking_query("how to apply for loan")
        True
        >>> is_banking_query("elon musk")
        False
    """
    # Normalize query for better cache hits
    query_normalized = query.lower().strip()
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast, cheap: $0.00015/1K tokens
            messages=[{
                "role": "system",
                "content": """You are a precise query classifier for a banking assistant.

Determine if the query is related to banking, finance, or financial products.

Banking-related queries:
- Bank names (SBI, HDFC, Axis, etc.)
- Products (cards, loans, accounts, schemes)
- Banking terms (fees, interest, eligibility, apply, balance)
- Financial procedures

Non-banking queries:
- Random words/names (e.g., "shivaram", "john")
- Celebrities/people (e.g., "elon musk")
- Dates/times (e.g., "27 jan", "today")
- General topics (weather, news, sports)
- Greetings are banking-related (return YES)

Respond with ONLY "YES" or "NO" - no explanations."""
            }, {
                "role": "user",
                "content": query_normalized
            }],
            temperature=0,  # Deterministic
            max_tokens=3,   # Only need 1 word
            timeout=5       # 5 second timeout
        )
        
        answer = response.choices[0].message.content.strip().upper()
        is_relevant = answer == "YES"
        
        logging.info(f"[Query Validator] '{query}' → {answer} (banking_related: {is_relevant})")
        return is_relevant
        
    except Exception as e:
        # Safe fallback: If LLM fails, assume query is valid
        # This prevents breaking the system if API is down
        logging.warning(f"[Query Validator] LLM failed for '{query}': {e}")
        logging.warning(f"[Query Validator] Defaulting to TRUE (safe mode)")
        return True


def clear_cache():
    """Clear the LRU cache (useful for testing)."""
    is_banking_query.cache_clear()
    logging.info("[Query Validator] Cache cleared")


if __name__ == "__main__":
    # Test cases
    logging.basicConfig(level=logging.INFO)
    
    test_cases = [
        # Should be TRUE (banking-related)
        ("SBI debit cards", True),
        ("how many loans", True),
        ("explain credit card", True),
        ("HDFC", True),
        ("apply for loan", True),
        ("interest rate", True),
        ("hello", True),  # Greeting
        
        # Should be FALSE (non-banking)
        ("shivaram", False),
        ("elon musk", False),
        ("27 jan", False),
        ("random word", False),
        ("weather today", False),
    ]
    
    print("\n" + "="*60)
    print("Query Validator Test Cases")
    print("="*60)
    
    for query, expected in test_cases:
        result = is_banking_query(query)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{query}' → {result} (expected: {expected})")
    
    print("\n" + "="*60)
    print(f"Cache Info: {is_banking_query.cache_info()}")
    print("="*60)
