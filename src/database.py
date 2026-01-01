import sqlite3
import json
import os
import logging
from src.config import DB_PATH

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = str(db_path) if db_path else str(DB_PATH)
        # Quick Win 2: Persistent connection to eliminate connection overhead (~50ms per query)
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._initialize_db()
    
    def __del__(self):
        """Cleanup persistent connection on object destruction"""
        if hasattr(self, '_connection'):
            self._connection.close()

    def _initialize_db(self):
        """Initializes the Tables. Translates our schema.sql to SQLite syntax."""
        cursor = self._connection.cursor()
        
        # 1. Products Table
        # Note: SQLite doesn't have native JSONB, so we store JSON as TEXT.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_name TEXT NOT NULL,
                category TEXT NOT NULL,
                product_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_file TEXT,
                attributes TEXT, -- Stored as JSON String
                summary_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bank_name, product_name)
            )
        """)
        
        # 2. Interaction Logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                query_text TEXT,
                intent_detected TEXT,
                response_generated TEXT,
                is_missed_query BOOLEAN DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Quick Win 3: Create indexes for query performance (~30-50ms improvement)
        self._create_indexes()
        
        self._connection.commit()
    
    def _create_indexes(self):
        """Create indexes on frequently queried columns to speed up WHERE clauses"""
        cursor = self._connection.cursor()
        
        # Composite index for most common query pattern: WHERE bank_name='X' AND category='Y'
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bank_category 
            ON products(bank_name, category)
        """)
        
        # Index for product name lookups (comparison queries, LIKE searches)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_name 
            ON products(product_name)
        """)
        
        # Index for category-only queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category 
            ON products(category)
        """)
        
        logging.info("✅ Database indexes created successfully")


    def upsert_product(self, product_data):
        """
        Inserts or Updates a product.
        product_data: dict containing keys matching table columns.
        attributes should be a Python dict (will be dumped to JSON string).
        """
        cursor = self._connection.cursor()
        
        attributes_json = json.dumps(product_data.get('attributes', {}))
        
        try:
            cursor.execute("""
                INSERT INTO products (bank_name, category, product_name, source_type, source_file, attributes, summary_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bank_name, product_name) DO UPDATE SET
                    attributes=excluded.attributes,
                    summary_text=excluded.summary_text,
                    source_file=excluded.source_file
            """, (
                product_data['bank_name'],
                product_data['category'],
                product_data['product_name'],
                product_data['source_type'],
                product_data.get('source_file'),
                attributes_json,
                product_data.get('summary_text')
            ))
            self._connection.commit()
            logging.info(f"✅ Upserted: {product_data['product_name']}")
        except Exception as e:
            logging.error(f"❌ DB Error upserting {product_data.get('product_name')}: {e}")

    def get_products_by_category_and_bank(self, category, bank=None):
        cursor = self._connection.cursor()
        
        query = "SELECT product_name, attributes, summary_text FROM products WHERE category = ?"
        params = [category]
        
        if bank:
            query += " AND bank_name = ?"
            params.append(bank)
            
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Parse JSON back to dict
        parsed_results = []
        for row in results:
            parsed_results.append({
                "product_name": row[0],
                "attributes": json.loads(row[1]) if row[1] else {},
                "summary_text": row[2]
            })
        return parsed_results

    def count_products(self, bank_name=None, category=None):
        cursor = self._connection.cursor()
        
        query = "SELECT COUNT(*) FROM products WHERE 1=1"
        params = []
        
        if bank_name:
            query += " AND bank_name = ?"
            params.append(bank_name)
        if category:
            query += " AND category = ?"
            params.append(category)
            
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        return count

# Initialize DB on import
if __name__ == "__main__":
    # If run directly, define a basic logger
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    print("Database Initialized.")
