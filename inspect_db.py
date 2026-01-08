import sqlite3
import sys

try:
    conn = sqlite3.connect('banking_assistant.db')
    cursor = conn.cursor()
    
    # Check total products
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    print(f"Total products in database: {total}")
    
    # Check debit cards
    cursor.execute("SELECT COUNT(*) FROM products WHERE category LIKE '%Debit%'")
    debit_count = cursor.fetchone()[0]
    print(f"Total debit cards: {debit_count}")
    
    # Check categories
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
    categories = cursor.fetchall()
    print(f"\nAll categories in database:")
    for cat in categories:
        print(f"  - {cat[0]}")
    
    # Sample a few products
    cursor.execute("SELECT bank_name, category, product_name FROM products LIMIT 10")
    print(f"\nSample products:")
    for row in cursor.fetchall():
        print(f"  {row[0]} | {row[1]} | {row[2]}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
