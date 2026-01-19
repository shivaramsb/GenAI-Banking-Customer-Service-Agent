"""
Comprehensive Test Suite for Follow-up Logic
Tests all edge cases to prevent production bugs
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.history_manager import HistoryStateManager, ContextState
from src.followup_router import FollowupRouter

# ============================================================================
# TEST DATA: Real bot responses from production
# ============================================================================

MOCK_HISTORIES = {
    "list_with_fees": [
        {'role': 'user', 'content': 'List HDFC cards'},
        {'role': 'assistant', 'content': '''📋 HDFC Debit Cards (10 total):

HDFC EasyShop Titanium - Rs. 250 + Taxes
HDFC EasyShop Woman - Rs. 200 + Taxes
HDFC Imperia - Nil
💡 Ask "explain [product name]" for details.'''}
    ],
    
    "list_without_fees": [
        {'role': 'user', 'content': 'List SBI cards'},
        {'role': 'assistant', 'content': '''📋 SBI Debit Cards (11 total):

SBI Debit Card
SBI Global International - Rs. 125 + Taxes
SBI Gold International - Rs. 175 + Taxes
💡 Ask "explain [product name]" for details.'''}
    ],
    
    "count_response": [
        {'role': 'user', 'content': 'How many HDFC cards?'},
        {'role': 'assistant', 'content': 'HDFC offers a total of 10 debit cards!'}
    ],
    
    "recommend_inline": [
        {'role': 'user', 'content': 'Best student card?'},
        {'role': 'assistant', 'content': 'The HDFC MoneyBack Debit Card might be a great option for students.'}
    ],
    
    "recommend_bullet": [
        {'role': 'user', 'content': 'Best travel card?'},
        {'role': 'assistant', 'content': '''Recommendations:

**HDFC Regalia** - This card is great for travel.
- Annual fee: Rs. 2500'''}
    ]
}

# ============================================================================
# TEST CASES
# ============================================================================

def test_ordinal_with_fees():
    """Test: 'Explain the first one' after listing products WITH fees"""
    print("\n--- TEST 1: Ordinal Selection (With Fees) ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    state = manager.extract_state(MOCK_HISTORIES['list_with_fees'])
    
    # Verify state extraction
    assert state.active_intent == 'LIST', f"Expected LIST, got {state.active_intent}"
    assert len(state.last_response_meta.get('product_names', [])) > 0, "No products extracted"
    assert state.last_response_meta['product_names'][0] == 'HDFC EasyShop Titanium', \
        f"First product wrong: {state.last_response_meta['product_names'][0]}"
    
    # Test followup
    result = router.route_followup("Explain the first one", state)
    assert result is not None, "Followup router returned None"
    assert result['intent'] == 'EXPLAIN', f"Expected EXPLAIN, got {result['intent']}"
    assert result['product_name'] == 'HDFC EasyShop Titanium', \
        f"Product name mismatch: {result['product_name']}"
    
    print("✅ PASSED")

def test_ordinal_without_fees():
    """Test: 'Explain the first one' after listing products WITHOUT fees"""
    print("\n--- TEST 2: Ordinal Selection (Without Fees) ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    state = manager.extract_state(MOCK_HISTORIES['list_without_fees'])
    
    # Verify state extraction
    assert state.active_intent == 'LIST', f"Expected LIST, got {state.active_intent}"
    products = state.last_response_meta.get('product_names', [])
    assert len(products) > 0, "No products extracted"
    assert products[0] == 'SBI Debit Card', f"First product wrong: {products[0]}"
    
    # Test followup
    result = router.route_followup("Explain the first one", state)
    assert result['product_name'] == 'SBI Debit Card', f"Product name mismatch: {result['product_name']}"
    
    print("✅ PASSED")

def test_count_to_list():
    """Test: 'List them' after COUNT response"""
    print("\n--- TEST 3: COUNT → LIST Transition ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    state = manager.extract_state(MOCK_HISTORIES['count_response'])
    
    assert state.active_intent == 'COUNT', f"Expected COUNT, got {state.active_intent}"
    
    result = router.route_followup("List them", state)
    assert result is not None, "Followup router returned None"
    assert result['intent'] == 'LIST', f"Expected LIST, got {result['intent']}"
    
    print("✅ PASSED")

def test_recommend_why_inline():
    """Test: 'Why?' after inline recommendation"""
    print("\n--- TEST 4: RECOMMEND → EXPLAIN (Inline) ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    state = manager.extract_state(MOCK_HISTORIES['recommend_inline'])
    
    assert state.active_intent == 'RECOMMEND', f"Expected RECOMMEND, got {state.active_intent}"
    recommended = state.last_response_meta.get('recommended_product')
    assert recommended is not None, "Failed to extract recommended product"
    assert 'MoneyBack' in recommended or 'HDFC' in recommended, f"Unexpected product: {recommended}"
    
    result = router.route_followup("why", state)
    assert result is not None, "Followup router returned None"
    assert result['intent'] == 'EXPLAIN', f"Expected EXPLAIN, got {result['intent']}"
    
    print("✅ PASSED")

def test_recommend_why_bullet():
    """Test: 'Why?' after bullet-point recommendation"""
    print("\n--- TEST 5: RECOMMEND → EXPLAIN (Bullet) ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    state = manager.extract_state(MOCK_HISTORIES['recommend_bullet'])
    
    assert state.active_intent == 'RECOMMEND', f"Expected RECOMMEND, got {state.active_intent}"
    recommended = state.last_response_meta.get('recommended_product')
    assert recommended is not None, f"Failed to extract recommended product"
    
    result = router.route_followup("why", state)
    assert result is not None, "Followup router returned None"
    
    print("✅ PASSED")

def run_all_tests():
    """Run all tests and report results"""
    tests = [
        test_ordinal_with_fees,
        test_ordinal_without_fees,
        test_count_to_list,
        test_recommend_why_inline,
        test_recommend_why_bullet
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"💥 ERROR: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*60}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
