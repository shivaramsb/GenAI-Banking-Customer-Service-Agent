"""
Comprehensive diagnostic to find COUNT vs LIST discrepancy
"""
import sys
sys.path.append('.')

from src.agent_core import process_query
from src.sql_tool import execute_sql_tool
import sqlite3
from src.config import DB_PATH

print("="*80)
print("DIAGNOSING COUNT vs LIST DISCREPANCY")
print("="*80)

# Step 1: Check actual database count
print("\n1. ACTUAL DATABASE STATE:")
print("-"*80)
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM products WHERE bank_name='HDFC' AND category='Credit Card'")
db_count = cursor.fetchone()[0]
print(f"Database COUNT: {db_count}")

cursor.execute("SELECT product_name FROM products WHERE bank_name='HDFC' AND category='Credit Card'")
products = cursor.fetchall()
print(f"Product names ({len(products)}):")
for p in products:
    print(f"  - {p[0]}")
conn.close()

# Step 2: Test COUNT query through sql_tool directly
print("\n\n2. SQL TOOL DIRECT TEST (COUNT):")
print("-"*80)
count_result = execute_sql_tool("How many HDFC credit cards", skip_synthesis=False)
print(f"SQL Generated: {count_result.get('sql')}")
print(f"Response Text: {count_result.get('text')}")
print(f"Data: {count_result.get('data')}")

# Step 3: Test LIST query through sql_tool
print("\n\n3. SQL TOOL DIRECT TEST (LIST):")
print("-"*80)
list_result = execute_sql_tool("List all HDFC credit cards", skip_synthesis=True)
print(f"SQL Generated: {list_result.get('sql')}")
print(f"Number of products returned: {len(list_result.get('data', []))}")

# Step 4: Test through agent_core (full path)
print("\n\n4. AGENT CORE TEST (COUNT):")
print("-"*80)
agent_count = process_query("How many HDFC credit cards")
print(f"Response: {agent_count.get('text')}")
print(f"Metadata: {agent_count.get('metadata', {})}")

print("\n\n5. AGENT CORE TEST (LIST):")
print("-"*80)
agent_list = process_query("List all HDFC credit cards")
print(f"Response snippet: {agent_list.get('text', '')[:200]}...")
print(f"Metadata: {agent_list.get('metadata', {})}")

print("\n\n" + "="*80)
print("DIAGNOSIS SUMMARY:")
print("="*80)
print(f"Database has: {db_count} HDFC credit cards")
print(f"COUNT query returns: [check output above]")
print(f"LIST query returns: [check output above]")
print("\nThe discrepancy is in how the queries are processed!")
