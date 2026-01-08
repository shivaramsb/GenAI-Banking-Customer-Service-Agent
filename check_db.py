import sqlite3

# Connect to the database
conn = sqlite3.connect('banking_assistant.db')
cursor = conn.cursor()

# Query to count debit cards
cursor.execute("""
    SELECT category, COUNT(*) as count 
    FROM products 
    WHERE category LIKE '%Debit%'
    GROUP BY category
""")

print("Debit Card Categories:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} products")

# Total debit cards
cursor.execute("SELECT COUNT(*) FROM products WHERE category LIKE '%Debit%'")
total = cursor.fetchone()[0]
conn.close()
