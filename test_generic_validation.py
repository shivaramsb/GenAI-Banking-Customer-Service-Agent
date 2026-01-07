"""
Test the generic query validation fix
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_core import process_query

# Test generic queries that should be caught
test_queries = [
    "bank",
    "card", 
    "loan",
    "product",
    "account"
]

print("=" * 80)
print("GENERIC QUERY VALIDATION TEST")
print("=" * 80)

for query in test_queries:
    print(f"\nQuery: '{query}'")
    result = process_query(query)
    source = result.get('source', 'Unknown')
    text_preview = result.get('text', '')[:100] + "..." if len(result.get('text', '')) > 100 else result.get('text', '')
    
    if source == "Clarification Needed":
        print(f"✅ CAUGHT - Source: {source}")
        print(f"   Response: {text_preview}")
    else:
        print(f"❌ MISSED - Source: {source}")

print("\n" + "=" * 80)
print("\n🧪 Testing valid queries don't get caught:")

valid_queries = ["hdfc credit cards", "what are the loans", "best card for students"]
for query in valid_queries:
    result = process_query(query)
    source = result.get('source', 'Unknown')
    if source == "Clarification Needed":
        print(f"❌ FALSE POSITIVE: '{query}' was incorrectly caught")
    else:
        print(f"✅ PASS: '{query}' → {source}")

print("=" * 80)
