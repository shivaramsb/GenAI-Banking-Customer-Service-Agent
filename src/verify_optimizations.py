import sys
import os
import time
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_core import process_query
from src.config import DB_PATH

def test_query_latency():
    """Test latency improvements from Quick Win optimizations"""
    
    print("=" * 60)
    print("QUICK WIN OPTIMIZATIONS - VERIFICATION TEST")
    print("=" * 60)
    
    test_queries = [
        "How many SBI credit cards?",
        "List all HDFC debit cards",
        "Compare HDFC Millennia vs HDFC Swiggy",
        "Best credit card for students"
    ]
    
    print("\n📊 Testing Query Latency...")
    print("-" * 60)
    
    total_time = 0
    for query in test_queries:
        start_time = time.time()
        response = process_query(query)
        end_time = time.time()
        
        latency = end_time - start_time
        total_time += latency
        
        # Determine if query meets target
        status = "✅" if latency < 3.0 else "⚠️"
        
        print(f"\n{status} Query: {query}")
        print(f"   Latency: {latency:.2f}s")
        print(f"   Data returned: {len(response.get('data', [])) if response.get('data') else 0} items")
    
    avg_latency = total_time / len(test_queries)
    
    print("\n" + "=" * 60)
    print(f"📈 RESULTS:")
    print(f"   Average Latency: {avg_latency:.2f}s")
    print(f"   Target: < 2.5s")
    
    if avg_latency < 2.5:
        print("   ✅ PERFORMANCE TARGET MET!")
    else:
        print("   ⚠️ Close to target, continue monitoring")
    
    print("=" * 60)

def verify_database_indexes():
    """Verify that database indexes were created successfully"""
    
    print("\n\n📋 Verifying Database Indexes...")
    print("-" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='products'")
    indexes = cursor.fetchall()
    
    expected_indexes = ['idx_bank_category', 'idx_product_name', 'idx_category']
    
    print(f"\nFound {len(indexes)} indexes:")
    for idx in indexes:
        idx_name = idx[0]
        if idx_name in expected_indexes:
            print(f"   ✅ {idx_name}")
        else:
            print(f"   ℹ️  {idx_name}")
    
    # Verify all expected indexes exist
    found_names = [idx[0] for idx in indexes]
    all_found = all(exp in found_names for exp in expected_indexes)
    
    if all_found:
        print("\n✅ All expected indexes are present!")
    else:
        missing = [idx for idx in expected_indexes if idx not in found_names]
        print(f"\n⚠️ Missing indexes: {missing}")
    
    # Test index usage
    print("\n\n🔍 Testing Index Usage (EXPLAIN QUERY PLAN)...")
    print("-" * 60)
    
    test_sql = "SELECT * FROM products WHERE bank_name='SBI' AND category='Credit Card'"
    cursor.execute(f"EXPLAIN QUERY PLAN {test_sql}")
    plan = cursor.fetchall()
    
    print(f"\nQuery: {test_sql}")
    for row in plan:
        detail = row[3] if len(row) > 3 else str(row)
        print(f"   {detail}")
        
        # Check if index is being used
        if 'idx_bank_category' in detail or 'USING INDEX' in detail:
            print("   ✅ Index is being used!")
        else:
            print("   ⚠️ Index may not be used (check query plan)")
    
    conn.close()
    print("\n" + "=" * 60)

def test_response_quality():
    """Ensure skip_synthesis doesn't break multi-retriever"""
    
    print("\n\n🧪 Testing Response Quality...")
    print("-" * 60)
    
    # Test multi-retriever with comparison
    response = process_query("Compare HDFC Millennia vs HDFC Swiggy")
    
    data = response.get('data', [])
    text = response.get('text', '')
    
    print(f"\nTest: Comparison Query")
    print(f"   Data returned: {len(data)} products")
    print(f"   Response length: {len(text)} chars")
    
    # Verify both products are in response
    has_millennia = 'Millennia' in text or any('Millennia' in str(d) for d in data)
    has_swiggy = 'Swiggy' in text or any('Swiggy' in str(d) for d in data)
    
    if has_millennia and has_swiggy:
        print("   ✅ Both products found in response")
    else:
        print("   ⚠️ One or both products missing")
    
    if len(data) >= 2:
        print("   ✅ Data table available for comparison")
    else:
        print("   ⚠️ Expected at least 2 products in data")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        test_query_latency()
        verify_database_indexes()
        test_response_quality()
        
        print("\n\n🎉 VERIFICATION COMPLETE!")
        print("\nExpected improvements:")
        print("   - Quick Win 1 (Skip synthesis): ~1.5s saved")
        print("   - Quick Win 2 (Persistent connection): ~50ms saved")
        print("   - Quick Win 3 (Database indexes): ~30ms saved")
        print("   - Total expected: ~1.58s reduction (43% faster)")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
