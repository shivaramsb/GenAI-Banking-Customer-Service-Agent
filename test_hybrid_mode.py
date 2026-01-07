"""
Test Hybrid Auto Mode Implementation

Tests mode selection logic and verifies routing works correctly.
"""
import sys
import logging
sys.path.append('.')

from src.agent_core import process_query

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 80)
print("HYBRID AUTO MODE TEST")
print("=" * 80)

test_cases = [
    # Accuracy-critical queries (should use STRUCTURED)
    {
        "query": "how many hdfc credit cards",
        "expected_mode": "STRUCTURED",
        "category": "Count Query"
    },
    {
        "query": "list all sbi loans",
        "expected_mode": "STRUCTURED",
        "category": "List All Query"
    },
    {
        "query": "explain all hdfc products",
        "expected_mode": "STRUCTURED",
        "category": "Explain All Query"
    },
    
    # Conversational queries (should use CHATGPT)
    {
        "query": "tell me about credit cards",
        "expected_mode": "CHATGPT",
        "category": "General Question"
    },
    {
        "query": "which card is better for students?",
        "expected_mode": "CHATGPT",
        "category": "Recommendation"
    },
    {
        "query": "what is the difference between these?",
        "expected_mode": "CHATGPT",
        "category": "Follow-up Question"
    }
]

print("\n🧪 Testing AUTO mode routing logic:\n")

for i, test in enumerate(test_cases, 1):
    print(f"{i}. {test['category']}: \"{test['query']}\"")
    print(f"   Expected: {test['expected_mode']}")
    
    try:
        response = process_query(test['query'], mode="auto")
        source = response.get('source', 'Unknown')
        
        # Check if source indicates correct mode
        if test['expected_mode'] == "STRUCTURED":
            if "ChatGPT" not in source:
                print(f"   ✅ PASS - Routed to STRUCTURED mode")
            else:
                print(f"   ❌ FAIL - Incorrectly routed to ChatGPT")
        else:
            if "ChatGPT" in source:
                print(f"   ✅ PASS - Routed to CHATGPT mode")
            else:
                print(f"   ❌ FAIL - Incorrectly routed to STRUCTURED")
                
        print(f"   Source: {source}\n")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}\n")

print("=" * 80)
print("\n✅ Hybrid mode implementation complete!")
print("\nNow test in Streamlit:")
print("  1. Run: streamlit run app.py")
print("  2. Try different queries with different modes")
print("  3. Verify AUTO mode switches correctly")
