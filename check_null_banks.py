# Check which products have NULL bank names
import sqlite3

conn = sqlite3.connect('c:/Users/babar/Desktop/genai_cust_agent/banking_assistant.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT product_name, bank_name, source_type, source_file
    FROM products 
    WHERE bank_name IS NULL OR bank_name = 'N/A' OR bank_name = ''
""")

null_products = cursor.fetchall()
print(f"Products with NULL/N/A bank names: {len(null_products)}")
for p in null_products:
    print(f"  {p[0]} | bank={p[1]} | source={p[2]}/{p[3]}")

conn.close()
