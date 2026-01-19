"""Quick test for context follow-up logic"""
import sys
sys.path.insert(0, '.')

from src.smart_router import smart_route, extract_context_from_history, extract_entities

print("="*60)
print("TESTING FOLLOW-UP CONTEXT MEMORY")
print("="*60)

# Test 1: Context extraction from history
print("\n1. Context Extraction Test:")
chat_history = [{'role': 'user', 'content': 'hdfc'}]
ctx = extract_context_from_history(chat_history)
print(f"   History: 'hdfc'")
print(f"   Extracted bank: {ctx.get('bank')}")

# Test 2: Entity extraction from current query
print("\n2. Entity Extraction Test:")
entities = extract_entities('debit card')
print(f"   Query: 'debit card'")
print(f"   Bank: {entities.get('bank')}")
print(f"   Category: {entities.get('category')}")

# Test 3: Partial term "credit"
print("\n3. Partial Term Test:")
entities2 = extract_entities('credit')
print(f"   Query: 'credit'")
print(f"   Category: {entities2.get('category')}")

# Test 4: Full smart_route with context (no LLM)
print("\n4. Smart Route with Context (may use LLM fallback):")
chat_history = [
    {'role': 'user', 'content': 'hdfc'},
    {'role': 'assistant', 'content': 'How can I help with HDFC?'}
]
# Skip actual smart_route to avoid LLM calls
ctx = extract_context_from_history(chat_history)
ent = extract_entities('debit card')
print(f"   History bank: {ctx.get('bank')}")
print(f"   Query category: {ent.get('category')}")
print(f"   Combined: bank={ctx.get('bank') or ent.get('bank')}, category={ent.get('category')}")

if ctx.get('bank') and ent.get('category'):
    print("   ✅ Should trigger IMPLICIT_LIST intent!")
else:
    print("   ❌ Missing context - will ask for clarification")

print("\n" + "="*60)
