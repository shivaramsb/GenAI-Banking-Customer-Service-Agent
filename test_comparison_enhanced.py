"""
Test enhanced comparison with partial names and smart suggestions
"""
import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')

from src.agent_core import process_query

print("="*80)
print("TESTING ENHANCED COMPARISON FEATURES")
print("="*80)

# Test 1: Partial names (GPT should handle this in SQL generation)
print("\n1. TEST: Compare Millennia vs Regalia (partial names)")
print("-"*80)
result = process_query("Compare Millennia vs Regalia")
print(result['text'][:600] + "...")

# Test 2: Full names (should definitely work)
print("\n\n2. TEST: HDFC Swiggy vs SBI SimplySave (full names)")
print("-"*80)
result = process_query("HDFC Swiggy vs SBI SimplySave")
print(result['text'][:600] + "...")

# Test 3: Wrong names (should give suggestions)
print("\n\n3. TEST: Compare XYZCard vs ABCCard (wrong names - should suggest)")
print("-"*80)
result = process_query("Compare XYZCard vs ABCCard")
print(result['text'][:600])

print("\n" + "="*80)
print("✅ TESTS COMPLETE - Review Results Above")
print("="*80)
print("\nExpected Results:")
print("- Test 1 & 2: Should show comparison table")
print("- Test 3: Should show suggestions with similar product names")
