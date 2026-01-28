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
    
    # === MULTI-OPERATION SUPPORT ===
    # If evidence router detected multiple operations, handle them
    operations = query_info.get('operations', [intent])
    
    if len(operations) > 1:
        logging.info(f"→ MULTI-OPERATION: {operations}")
        return handle_multi_operation(query_info, effective_query, chat_history)
    
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
        
        # Detect conversational/greeting queries - route to ChatGPT for natural handling
        conversational_patterns = [
            'who are you', 'what are you', 'who r u',
            'how are you', 'how r u', 'how are u',
            'what is your name', 'tell me about yourself',
            'introduce yourself', 'what do you do',
            'how life', 'how is life', 'what\'s up', 'wassup',
            'good morning', 'good afternoon', 'good evening',
            'nice to meet', 'pleasure to meet'
        ]
        
        query_lower = user_query.lower()
        is_conversational = any(pattern in query_lower for pattern in conversational_patterns)
        
        # If conversational, use ChatGPT for natural response
        if is_conversational:
            logging.info("→ CLARIFY: Conversational query detected, routing to ChatGPT")
            return chatgpt_query(
                user_query, 
                chat_history, 
                clarification_mode=True,  # Special mode for conversational queries
                intent='CONVERSATIONAL'
            )
        
        # Normal clarification for vague banking queries
        # Natural language response based on what was detected
        if category:
            response_text = f"I can help you with {category}s! Which bank are you interested in - SBI, HDFC, or Axis? Or would you like me to compare options across banks?"
        else:
            response_text = "Hello! 👋 I'm your Banking Assistant, I'd be happy to help! Are you looking for debit cards,credit cards, loans, or something else? And which bank - SBI, HDFC, or Axis?"
        
        return {
            "text": response_text,
            "source": "Clarification",
            "data": [],
            "metadata": {"routing_path": routing_path}
        }
    
    # REFUSE - Non-banking query with context detected
    if intent == 'REFUSE':
        logging.info(f"→ ROUTING: REFUSE (non-banking query with context)")
        # Route to ChatGPT for natural, polite redirection
        return chatgpt_query(
            user_query,
            chat_history,
            clarification_mode=True,
            intent='CONVERSATIONAL'  # Use same natural handling
        )
    
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
    
    # Fallback: ChatGPT
    logging.info("→ ROUTING: FALLBACK (intent=UNKNOWN)")
    return chatgpt_query(effective_query, chat_history, clarification_mode=False)



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
# MULTI-OPERATION HANDLER
# =============================================================================

def handle_multi_operation(query_info: dict, effective_query: str, chat_history: list) -> dict:
    """
    Execute multiple operations and merge results.
    
    Example: "how many SBI cards and how to apply"
    Operations: ['COUNT', 'FAQ']
    Result: Combined response with count + application procedure
    """
    operations = query_info['operations']
    results = []
    
    logging.info(f"[Multi-Op] Executing {len(operations)} operations: {operations}")
    
    for op in operations:
        try:
            if op == 'COUNT':
                result = handle_count_query(query_info)
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ COUNT executed")
            
            elif op == 'LIST':
                result = handle_list_query(query_info)
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ LIST executed")
            
            elif op == 'EXPLAIN' or op == 'EXPLAIN_ALL':
                result = handle_explain_query(query_info)
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ EXPLAIN executed")
            
            
            
            elif op == 'FAQ':
                # In multi-op with COUNT/LIST, extract only the FAQ-related part
                suppress_count = 'COUNT' in operations or 'LIST' in operations
                faq_query = effective_query
                
                if suppress_count:
                    # Extract FAQ keywords from query
                    import re
                    faq_keywords = ['apply', 'application', 'document', 'requirement', 
                                   'eligibility', 'process', 'procedure', 'steps', 'how to']
                    
                    # Find FAQ-related parts
                    query_lower = effective_query.lower()
                    matched_keywords = [kw for kw in faq_keywords if kw in query_lower]
                    
                    if matched_keywords:
                        # Build a focused FAQ query
                        bank_category_parts = []
                        if query_info.get('bank'):
                            bank_category_parts.append(query_info['bank'])
                        if query_info.get('category'):
                            bank_category_parts.append(query_info['category'])
                        
                        # Construct: "how to apply for SBI credit cards"
                        context = ' '.join(bank_category_parts) if bank_category_parts else "this product"
                        faq_query = f"how to {matched_keywords[0]} for {context}"
                        logging.info(f"[Multi-Op] Extracted FAQ query: '{faq_query}'")
                
                result = chatgpt_query(faq_query, chat_history, clarification_mode=False, intent='FAQ', suppress_count=suppress_count)
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ FAQ executed (suppress_count={suppress_count})")
            
            elif op == 'COMPARE':
                result = chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='COMPARE')
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ COMPARE executed")
            
            elif op == 'RECOMMEND':
                result = chatgpt_query(effective_query, chat_history, clarification_mode=False, intent='RECOMMEND')
                results.append(result['text'])
                logging.info(f"[Multi-Op] ✅ RECOMMEND executed")
        
        except Exception as e:
            logging.error(f"[Multi-Op] ❌ {op} failed: {e}")
            continue
    
    # Merge results with clear separation
    merged_text = "\n\n---\n\n".join(results) if results else "I encountered an error processing your request."
    
    return {
        "text": merged_text,
        "source": "Multi-Operation",
        "data": [],
        "metadata": {
            "operations": operations,
            "routing_path": query_info.get('routing_path', 'MULTI_OP')
        }
    }


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
