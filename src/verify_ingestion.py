import sys
import os

sys.path.append(os.getcwd())

from src.vector_db import FAQVectorDB
from src.database import DatabaseManager

def verify():
    print("🔍 Verifying Data Ingestion...")
    
    # 1. Check Vector DB
    vdb = FAQVectorDB()
    # Query for SBI
    sbi_res = vdb.query_faqs("account", bank_filter="SBI")
    print(f"SBI Retrieval Test (query='account'): Found {len(sbi_res)} results")
    if len(sbi_res) > 0:
        print(f"   Sample: {sbi_res[0].get('question')}")
        
    # Query for HDFC
    hdfc_res = vdb.query_faqs("account", bank_filter="HDFC")
    print(f"HDFC Retrieval Test (query='account'): Found {len(hdfc_res)} results")
    if len(hdfc_res) > 0:
        print(f"   Sample: {hdfc_res[0].get('question')}")

    # 2. Check SQL DB
    db = DatabaseManager()
    sbi_count = db.count_products("SBI")
    hdfc_count = db.count_products("HDFC")
    
    print(f"SQL Product Counts: SBI={sbi_count}, HDFC={hdfc_count}")
    
    if len(sbi_res) > 0 and len(hdfc_res) > 0 and sbi_count > 0 and hdfc_count > 0:
        print("✅ VERIFICATION SUCCESS: Both banks have data.")
    else:
        print("❌ VERIFICATION FAILED: Missing data.")

if __name__ == "__main__":
    verify()
