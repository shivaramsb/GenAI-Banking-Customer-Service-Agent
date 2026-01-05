"""Quick manual test"""
import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')
from src.agent_core import process_query

# Test wrong names - should now show suggestions
result = process_query("Compare XYZCard vs ABCCard")
print(result['text'])
