import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Project Paths ---
# Base directory is the project root (calculated relative to this file in src/)
BASE_DIR = Path(__file__).parent.parent.resolve()

DATA_DIR = BASE_DIR / "data"
PRODUCTS_DIR = DATA_DIR / "products"  # NEW: Organized products folder
FAQS_DIR = DATA_DIR / "faqs"          # NEW: Organized FAQs folder
DOCS_DIR = DATA_DIR / "docs"
CHROMADB_DIR = BASE_DIR / "chromadb_data"

# SQLite DB File
DB_NAME = "banking_assistant.db"
DB_PATH = BASE_DIR / DB_NAME

# --- Model Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Default to gpt-4o. We explicitly override os.getenv if it holds a legacy Llama value to prevent errors.
env_model = os.getenv("LLM_MODEL", "gpt-4o")
if "llama" in env_model.lower():
    LLM_MODEL = "gpt-4o"
else:
    LLM_MODEL = env_model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Constants ---
# You can add other constants here (e.g., Collection Names)
CHROMA_COLLECTION_NAME = "bank_faqs"

# --- Banking Configuration ---
# Dynamic configuration - queries database for actual banks/categories

def get_supported_banks_from_db():
    """Query database for all banks with products"""
    try:
        from src.database import DatabaseManager
        db = DatabaseManager()
        result = db.execute_raw_query("SELECT DISTINCT bank_name FROM products WHERE bank_name IS NOT NULL ORDER BY bank_name")
        banks = [row['bank_name'] for row in result]
        return banks if banks else ['SBI', 'HDFC']  # Fallback to defaults
    except:
        # Fallback if DB not initialized yet
        return ['SBI', 'HDFC']

def get_product_categories_from_db():
    """Query database for all product categories"""
    try:
        from src.database import DatabaseManager
        db = DatabaseManager()
        result = db.execute_raw_query("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category")
        categories = [row['category'] for row in result]
        return categories if categories else ['Credit Card', 'Debit Card', 'Loan', 'Scheme']
    except:
        # Fallback if DB not initialized yet
        return ['Credit Card', 'Debit Card', 'Loan', 'Scheme']

# Dynamic lists - update by re-running ingestion
SUPPORTED_BANKS = get_supported_banks_from_db()
PRODUCT_CATEGORIES = get_product_categories_from_db()

# Display names - add new banks here manually if needed
BANK_DISPLAY_NAMES = {
    'SBI': 'State Bank of India',
    'HDFC': 'HDFC Bank',
    'ICICI': 'ICICI Bank',
    'Axis': 'Axis Bank',
    'Kotak': 'Kotak Mahindra Bank',
    'IndusInd': 'IndusInd Bank'
}

# --- Helper Functions ---
def get_bank_list_sql():
    """Returns formatted bank list for SQL IN clause: 'SBI', 'HDFC'"""
    return ', '.join(f"'{bank}'" for bank in SUPPORTED_BANKS)

def get_banks_display():
    """Returns human-readable bank names: 'State Bank of India and HDFC Bank'"""
    names = [BANK_DISPLAY_NAMES.get(bank, bank) for bank in SUPPORTED_BANKS]
    if len(names) == 1:
        return names[0]
    elif len(names) == 2:
        return f"{names[0]} and {names[1]}"
    else:
        return ', '.join(names[:-1]) + f", and {names[-1]}"

def get_banks_short():
    """Returns short bank names: 'SBI and HDFC' or 'SBI/HDFC'"""
    if len(SUPPORTED_BANKS) == 2:
        return f"{SUPPORTED_BANKS[0]} and {SUPPORTED_BANKS[1]}"
    else:
        return '/'.join(SUPPORTED_BANKS)

def get_categories_display():
    """Returns category list: 'Credit Cards, Debit Cards, Loans'"""
    # Pluralize for display
    display_cats = []
    for cat in PRODUCT_CATEGORIES:
        if cat == 'Scheme':
            display_cats.append('Schemes')
        else:
            display_cats.append(cat + 's')
    return ', '.join(display_cats)

if __name__ == "__main__":
    # Test paths
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"DB_PATH: {DB_PATH}")
    print(f"LLM_MODEL: {LLM_MODEL}")
    print(f"\nBanking Config:")
    print(f"Banks: {SUPPORTED_BANKS}")
    print(f"Display: {get_banks_display()}")
    print(f"Short: {get_banks_short()}")
    print(f"Categories: {get_categories_display()}")
