import sqlite3

conn = sqlite3.connect('banking_assistant.db')
cursor = conn.cursor()

# Count total HDFC credit cards
cursor.execute("SELECT COUNT(*) FROM products WHERE bank_name='HDFC' AND category LIKE '%Credit Card%'")
total = cursor.fetchone()[0]
print(f"Total HDFC Credit Cards in database: {total}")

# List all HDFC credit cards
cursor.execute("SELECT product_name FROM products WHERE bank_name='HDFC' AND category LIKE '%Credit Card%' ORDER BY product_name")
cards = cursor.fetchall()

print(f"\nAll {len(cards)} HDFC Credit Cards:")
for i, (name,) in enumerate(cards, 1):
    print(f"{i}. {name}")

conn.close()
