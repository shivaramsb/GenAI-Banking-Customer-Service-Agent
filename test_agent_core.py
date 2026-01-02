"""
Test through the FULL agent_core path (what Streamlit uses)
"""
import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')

from src.agent_core import process_query

print("="*80)
print("TESTING THROUGH AGENT_CORE (Full Streamlit Path)")
print("="*80)

# Test COUNT through agent_core
print("\n1. COUNT Query through agent_core:")
count_response = process_query("How many HDFC credit cards")
print(f"   Text: {count_response.get('text')}")
print(f"   Data: {count_response.get('data')}")
print(f"   Metadata: {count_response.get('metadata')}")

# Test LIST through agent_core
print("\n2. LIST Query through agent_core:")
list_response = process_query("List all HDFC credit cards")
print(f"   Text (first 200 chars): {list_response.get('text', '')[:200]}")
print(f"   Data count: {len(list_response.get('data', []))}")
print(f"   Metadata: {list_response.get('metadata')}")

print("\n" + "="*80)
print("SHARE THIS OUTPUT - it will show where '15' comes from!")
print("="*80)
