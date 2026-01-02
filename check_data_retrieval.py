"""
Check what data is actually in the database vs what's being retrieved
"""
import sqlite3

conn = sqlite3.connect('c:/Users/babar/Desktop/genai_cust_agent/banking_assistant.db')
cursor = conn.cursor()

print("="*80)
print("DATABASE CONTENT CHECK")
print("="*80)

# Check first product in detail
cursor.execute("""
    SELECT product_name, bank_name, category, attributes, source_type
    FROM products 
    WHERE bank_name='HDFC' AND category='Credit Card'
    LIMIT 1
""")
product = cursor.fetchone()
print(f"\nFirst HDFC Credit Card in DB:")
print(f"  Product Name: {product[0]}")
print(f"  Bank Name: {product[1]}")
print(f"  Category: {product[2]}")
print(f"  Attributes: {product[3][:200]}...")  # First 200 chars
print(f"  Source: {product[4]}")

# Check what SQL the tool generates
print("\n" + "="*80)
print("SQL TOOL QUERY CHECK")
print("="*80)

import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')
from src.sql_tool import execute_sql_tool

result = execute_sql_tool("List all HDFC credit cards", skip_synthesis=True)
print(f"\nSQL Generated: {result['sql']}")
print(f"\nFirst result keys: {list(result['data'][0].keys())}")
print(f"\nFirst result:")
import json
print(json.dumps(result['data'][0], indent=2, default=str))

conn.close()
