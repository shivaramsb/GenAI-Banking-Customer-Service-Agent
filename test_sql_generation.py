"""
Run this in Python shell to see exact SQL and responses
"""
import sys
sys.path.append('c:/Users/babar/Desktop/genai_cust_agent')

# Test 1: Direct database check
print("="*80)
print("1. DATABASE REALITY CHECK")
print("="*80)
import sqlite3
conn = sqlite3.connect('c:/Users/babar/Desktop/genai_cust_agent/banking_assistant.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM products WHERE bank_name='HDFC' AND category='Credit Card'")
actual_count = cursor.fetchone()[0]
print(f"Database COUNT: {actual_count}")

cursor.execute("SELECT product_name FROM products WHERE bank_name='HDFC' AND category='Credit Card'")
names = [row[0] for row in cursor.fetchall()]
print(f"Product names ({len(names)}):")
for name in sorted(names):
    print(f"  {name}")
conn.close()

# Test 2: SQL Tool generates what SQL?
print("\n" + "="*80)
print("2. SQL GENERATION TEST")
print("="*80)

from src.sql_tool import execute_sql_tool

print("\nCOUNT Query:")
count_resp = execute_sql_tool("How many HDFC credit cards", skip_synthesis=False)
print(f"  SQL: {count_resp.get('sql')}")
print(f"  Text: {count_resp.get('text')}")

print("\nLIST Query:")
list_resp = execute_sql_tool("List all HDFC credit cards", skip_synthesis=True) 
print(f"  SQL: {list_resp.get('sql')}")
print(f"  Data count: {len(list_resp.get('data', []))}")

print("\n" + "="*80)
print("COPY THIS OUTPUT AND SHARE IT")
print("="*80)
