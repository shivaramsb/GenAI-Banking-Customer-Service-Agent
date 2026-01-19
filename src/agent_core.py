"""
Agent Core - Main Query Orchestrator

Uses the smart_router for intelligent query routing:
- GREETING, CLARIFY → Instant responses
- COUNT, LIST, EXPLAIN_ALL → Guaranteed accuracy handlers
- FAQ, COMPARE, RECOMMEND, FOLLOWUP → ChatGPT conversational
- UNKNOWN → ChatGPT fallback
"""

import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import json
from openai import OpenAI

from src.config import (
    OPENAI_API_KEY, LLM_MODEL,
    get_banks_short, get_categories_display
)
from src.multi_retriever import MultiSourceRetriever
from src.chatgpt_agent import chatgpt_query
from src.smart_router import smart_route  # Direct import of smart router

# Initialize OpenAI and Multi-Source Retriever
client = OpenAI(api_key=OPENAI_API_KEY)
retriever = MultiSourceRetriever()


def process_query(user_query, user_id="guest", chat_history=None, mode="auto"):
    """
    Main Query Orchestrator using Smart Router.
    
    Routes queries through 4-step hybrid routing:
    1. Accuracy-critical (COUNT/LIST/EXPLAIN_ALL) → Python handlers
    2. FAQ similarity → ChatGPT with FAQ context
    3. Other intents → ChatGPT conversational
    4. Unknown → ChatGPT fallback
    
    Args:
        user_query: User's question
        user_id: User identifier
        chat_history: Conversation history
        mode: Ignored (always uses smart routing)
    
    Returns:
        Response dict with text, source, data, metadata
    """
    logging.info(f"Processing query: {user_query}")
    
    # === SMART ROUTER CLASSIFICATION ===
    query_info = smart_route(user_query, chat_history)
    
    # Check for Virtual Query (e.g., Follow-up rewrite)
    # If FollowupRouter rewrote the query, use that for downstream processing
    effective_query = query_info.get('original_query', user_query)
    if effective_query != user_query:
        logging.info(f"→ VIRTUAL QUERY: '{user_query}' mapped to '{effective_query}'")
    
    intent = query_info['intent']
    confidence = query_info['confidence']
    routing_path = query_info.get('routing_path', 'UNKNOWN')
    
    logging.info(f"→ SMART ROUTER: Intent={intent}, Confidence={confidence:.2f}, Path={routing_path}")
    
    # === ROUTE BASED ON INTENT ===
    
    # GREETING
    if intent == 'GREETING':
        logging.info("→ ROUTING: GREETING")
        return {
            "text": f"Hello! 👋 I'm your Banking Assistant for {get_banks_short()}.\n\nI can help you with:\n- 💳 Credit & Debit Cards\n- 🏠 Loans (Home, Personal, Car)\n- 💰 Savings Accounts & Schemes\n- ❓ Banking procedures & FAQs\n\nHow can I assist you today?",
            "source": "Greeting",
            "data": [],
            "metadata": {"routing_path": routing_path}
        }
    
    # CLARIFY - Missing bank/category context
    if intent == 'CLARIFY':
        category = query_info.get('category')
        logging.info(f"→ ROUTING: CLARIFY")
        
        # Natural language response based on what was detected
        if category:
            response_text = f"I can help you with {category}s! Which bank are you interested in - SBI, HDFC, or Axis? Or would you like me to compare options across banks?"
        else:
            response_text = "I'd be happy to help! Are you looking for debit cards,credit cards, loans, or something else? And which bank - SBI, HDFC, or Axis?"
        
        return {
            "text": response_text,
            "source": "Clarification",
            "data": [],
            "metadata": {"routing_path": routing_path}
        }
    
    # COUNT - Guaranteed accuracy
    if intent == 'COUNT':
        logging.info("→ ROUTING: COUNT (guaranteed accuracy)")
        return handle_count_query(query_info)
    
    # LIST - Guaranteed completeness
    if intent == 'LIST':
        logging.info("→ ROUTING: LIST (guaranteed completeness)")
        return handle_list_query(query_info)
    
    # EXPLAIN_ALL - All products with details
    if intent == 'EXPLAIN_ALL':
        logging.info("→ ROUTING: EXPLAIN_ALL (guaranteed completeness)")
        return handle_explain_query(query_info)
    
    # EXPLAIN - Single product/category
    if intent == 'EXPLAIN':
        logging.info("→ ROUTING: EXPLAIN")
        return handle_explain_query(query_info)
    
    # FAQ - ChatGPT with FAQ context
    if intent == 'FAQ':
        logging.info("→ ROUTING: FAQ (ChatGPT)")
        return chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='FAQ')
    
    # COMPARE
    if intent == 'COMPARE':
        logging.info("→ ROUTING: COMPARE (ChatGPT)")
        return chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='COMPARE')
    
    # RECOMMEND
    if intent == 'RECOMMEND':
        logging.info("→ ROUTING: RECOMMEND (ChatGPT)")
        return chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='RECOMMEND')
    
    # FOLLOWUP
    if intent == 'FOLLOWUP':
        logging.info("→ ROUTING: FOLLOWUP (ChatGPT with history)")
        return chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='FOLLOWUP')
    
    # UNKNOWN or fallback
    logging.info(f"→ ROUTING: FALLBACK (intent={intent})")
    return chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='UNKNOWN')


# =============================================================================
# ACCURACY-CRITICAL HANDLERS
# =============================================================================

def handle_count_query(query_info: dict) -> dict:
    """
    Handle COUNT queries with guaranteed accuracy.
    Uses pure Python counting (no LLM hallucination).
    """
    from src.response_formatters import format_count_response
    
    bank = query_info.get('bank')
    category = query_info.get('category')
    
    logging.info(f"[COUNT Handler] Bank={bank}, Category={category}")
    
    products = retriever.get_all_products(bank=bank, category=category)
    return format_count_response(products, query_info)


def handle_list_query(query_info: dict) -> dict:
    """
    Handle LIST queries with guaranteed completeness.
    Uses pure Python formatting to ensure ALL products are listed.
    """
    from src.response_formatters import format_list_response
    
    bank = query_info.get('bank')
    category = query_info.get('category')
    
    query_lower = query_info.get('original_query', '').lower()
    detailed = 'detail' in query_lower or 'explain' in query_lower
    
    logging.info(f"[LIST Handler] Bank={bank}, Category={category}, Detailed={detailed}")
    
    products = retriever.get_all_products(bank=bank, category=category)
    return format_list_response(products, query_info, detailed=detailed)


def handle_explain_query(query_info: dict) -> dict:
    """
    Handle EXPLAIN/EXPLAIN_ALL queries with controlled LLM.
    Uses LLM with strict validation to ensure all products are explained.
    """
    from src.response_formatters import format_explain_response
    
    bank = query_info.get('bank')
    category = query_info.get('category')
    product_name = query_info.get('product_name')
    
    logging.info(f"[EXPLAIN Handler] Bank={bank}, Category={category}, Product={product_name}")
    
    if product_name:
        all_products = retriever.get_all_products(bank=bank, category=category)
        products = [p for p in all_products if product_name.lower() in p.get('product_name', '').lower()]
    else:
        products = retriever.get_all_products(bank=bank, category=category)
    
    return format_explain_response(products, query_info, client)


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🤖 Banking Agent CLI (Type 'quit' to exit)")
    history = []
    
    while True:
        q = input("\nYou: ")
        if q.lower() == "quit":
            break
        
        history.append({"role": "user", "content": q})
        
        response_obj = process_query(q, chat_history=history)
        
        if isinstance(response_obj, dict):
            ans_text = response_obj.get("text", "")
            source = response_obj.get("source", "")
            print(f"Agent ({source}): {ans_text}")
        else:
            ans_text = str(response_obj)
            print(f"Agent: {ans_text}")
        
        history.append({"role": "assistant", "content": ans_text})
