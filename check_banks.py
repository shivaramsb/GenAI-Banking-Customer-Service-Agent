from src.database import DatabaseManager
from src.config import SUPPORTED_BANKS

db = DatabaseManager()

print("=" * 60)
print("BANK DISTRIBUTION BY CATEGORY")
print("=" * 60)

# Get products by bank and category
result = db.execute_raw_query("""
    SELECT bank_name, category, COUNT(*) as count 
    FROM products 
    GROUP BY bank_name, category 
    ORDER BY bank_name, category
""")

# Print results
current_bank = None
for row in result:
    if row['bank_name'] != current_bank:
        if current_bank is not None:
            print()
        current_bank = row['bank_name']
        print(f"\n📊 {row['bank_name']}:")
    print(f"   {row['category']:20s} - {row['count']} products")

# Get total by bank
print("\n" + "=" * 60)
print("TOTAL PRODUCTS PER BANK")
print("=" * 60)
result2 = db.execute_raw_query("""
    SELECT bank_name, COUNT(*) as count 
    FROM products 
    GROUP BY bank_name 
    ORDER BY bank_name
""")

for row in result2:
    print(f"{row['bank_name']:10s} - {row['count']:3d} products")

# Check config
print("\n" + "=" * 60)
print("BANKS IN CONFIG")
print("=" * 60)
print(f"SUPPORTED_BANKS in config: {SUPPORTED_BANKS}")
print(f"Total banks configured: {len(SUPPORTED_BANKS)}")
