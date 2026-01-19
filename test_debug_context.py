
import logging
from src.history_manager import HistoryStateManager, ContextState
from src.followup_router import FollowupRouter

# Mock Data
MOCK_HISTORY_LIST = [
    {'role': 'user', 'content': 'List HDFC Debit Cards'},
    {'role': 'assistant', 'content': '📋 HDFC Debit Cards (10 total):\n\n1. HDFC EasyShop Titanium - Rs. 250\n2. HDFC Millennia - Rs. 500'}
]

MOCK_HISTORY_REC = [
    {'role': 'user', 'content': 'Best student card?'},
    {'role': 'assistant', 'content': 'Recommendations:\n\nHDFC EasyShop Titanium is great for students.'}
]

def test_flow_1_ordinal():
    print("\n--- TEST FLOW 1: Ordinal Selection ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    # 1. State Extraction
    state = manager.extract_state(MOCK_HISTORY_LIST)
    print(f"State: Intent={state.active_intent}, Products={state.last_response_meta.get('product_names')}")
    
    # 2. Router Check
    query = "Explain the first one"
    result = router.route_followup(query, state)
    print(f"Query: '{query}' -> Result: {result}")

def test_flow_2_recommend():
    print("\n--- TEST FLOW 2: Recommend Followup ---")
    manager = HistoryStateManager()
    router = FollowupRouter()
    
    # 1. State Extraction
    state = manager.extract_state(MOCK_HISTORY_REC)
    print(f"State: Intent={state.active_intent}")
    
    # 2. Router Check
    query = "why"
    result = router.route_followup(query, state)
    print(f"Query: '{query}' -> Result: {result}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    test_flow_1_ordinal()
    test_flow_2_recommend()
