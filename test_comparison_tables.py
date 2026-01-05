"""
Test comparison table feature
"""
import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')

from src.agent_core import process_query

print("="*80)
print("TESTING COMPARISON TABLE FEATURE")
print("="*80)

# Test 1: Compare 2 products
print("\n1. TEST: Compare HDFC Millennia vs Regalia")
print("-"*80)
result = process_query("Compare HDFC Millennia vs Regalia")
print(result['text'])

# Test 2: Compare with 'vs'
print("\n2. TEST: HDFC Swiggy vs SBI SimplySave")
print("-"*80)
result = process_query("HDFC Swiggy vs SBI SimplySave")
print(result['text'])

# Test 3: Compare 3 products
print("\n3. TEST: Compare HDFC Infinia vs Diners Black vs SBI Aurum")
print("-"*80)
result = process_query("Compare HDFC Infinia vs Diners Black vs SBI Aurum")
print(result['text'])

print("\n" + "="*80)
print("TESTS COMPLETE")
print("="*80)
