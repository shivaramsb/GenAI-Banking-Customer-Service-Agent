import logging
import os
import sys

# Add project root to path so we can import 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import json
from openai import OpenAI

from src.config import (
    OPENAI_API_KEY, LLM_MODEL,
    SUPPORTED_BANKS, PRODUCT_CATEGORIES,
    get_banks_short, get_categories_display
)
from src.multi_retriever import MultiSourceRetriever
from src.chatgpt_agent import chatgpt_query  # Import ChatGPT-style handler

# Initialize OpenAI and Multi-Source Retriever
client = OpenAI(api_key=OPENAI_API_KEY)
retriever = MultiSourceRetriever()

def process_query(user_query, user_id="guest", chat_history=None, mode="auto"):
    """
    Main Orchestrator with Hybrid Mode Support.
    
    Args:
        user_query: User's question
        user_id: User identifier
        chat_history: Conversation history
        mode: Response mode - "auto", "structured", or "chatgpt"
            - auto: Intelligently chooses based on query type (default)
            - structured: Always use structured responses (guaranteed accuracy)
            - chatgpt: Always use ChatGPT-style conversations
    
    Returns:
        Response dict with text, source, data, metadata
    """
    logging.info(f"Processing query: {user_query} [mode={mode}]")
    
    # === QUERY VALIDATION ===
    query_lower = user_query.lower().strip()
    
    # Check for greetings
    if query_lower in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'namaste']:
        return {
            "text": "Hello! 👋 I can help you with banking products.",
            "source": "Greeting",
            "data": [],
            "metadata": {}
        }
    
    # Check if query has banking context
    banking_keywords = [
        'card', 'credit', 'debit', 'loan', 'account', 'bank', 
        'hdfc', 'sbi', 'how', 'what', 'best', 'compare', 'list', 'show'
    ]
    has_context = any(kw in query_lower for kw in banking_keywords)
    
    # Reject gibberish (no context + very short)
    if not has_context and len(query_lower.split()) <= 3:
        return {
            "text": "❓ I didn't understand that. I'm a banking assistant.",
            "source": "Invalid Query",
            "data": [],
            "metadata": {}
        }
    
    # FIX: Detect overly generic single-word queries
    # Queries like "bank", "card", "loan" alone are too vague and lead to incomplete results
    generic_words = ['bank', 'card', 'loan', 'product', 'account', 'banking']
    query_words = query_lower.split()
    
    if len(query_words) == 1 and query_lower in generic_words:
        return {
            "text": f"💡 Could you be more specific?\n\n**Try asking:**\n• 'HDFC credit cards'\n• 'List all {SUPPORTED_BANKS[0]} loans'\n• 'What are the products?'\n\n**Supported banks:** {get_banks_short()}",
            "source": "Clarification Needed",
            "data": [],
            "metadata": {}
        }
    
    # === HYBRID MODE ROUTING ===
    # Auto mode: Intelligently choose structured vs ChatGPT based on query type
    if mode == "auto":
        # Accuracy-critical queries → use structured mode for guaranteed correctness
        accuracy_critical_keywords = [
            'how many', 'count', 'number of',  # Count queries
            'list all', 'explain all', 'show all', 'give me all',  # Complete listing
            'all the', 'every', 'complete list'
        ]
        
        needs_structured = any(keyword in query_lower for keyword in accuracy_critical_keywords)
        
        if needs_structured:
            logging.info("→ AUTO MODE: Using STRUCTURED (accuracy-critical query)")
            selected_mode = "structured"
        else:
            logging.info("→ AUTO MODE: Using CHATGPT (conversational query)")
            selected_mode = "chatgpt"
    else:
        selected_mode = mode
        logging.info(f"→ MANUAL MODE: {selected_mode.upper()}")
    
    # Route to appropriate handler
    if selected_mode == "chatgpt":
        # Use ChatGPT-style conversational handler
        return chatgpt_query(user_query, chat_history)
    
    # Otherwise, continue with structured mode below
    # (All the existing agent_core logic remains unchanged)
    
    # === MULTI-SOURCE RETRIEVAL ===
    # Search ALL sources in parallel (SQL + FAQ)
    # For comprehensive queries, increase max_results to avoid truncation
    query_lower = user_query.lower().strip()
    
    # FIX: Improved detection for comprehensive listing queries
    # Strategy: Detect both explicit listing phrases AND implicit category queries
    
    # Explicit listing phrases
    explicit_list_phrases = [
        'all', 'list all', 'explain all', 'list of', 'show me all',
        'what are the', 'what are all', 'which', 'show me',  # Changed "show me the" to "show me"
        'give me', 'tell me about'
    ]
    
    # Product category keywords that typically expect comprehensive results
    # e.g., "hdfc credit cards" is implicitly asking for ALL hdfc credit cards
    product_keywords = [
        'credit card', 'debit card', 'loan', 'account', 
        'cards', 'loans', 'products'  # Plural forms often mean "all"
    ]
    
    has_explicit_phrase = any(phrase in query_lower for phrase in explicit_list_phrases)
    has_product_plural = any(keyword in query_lower for keyword in product_keywords)
    
    # If query contains a bank name + product category keyword, it's likely asking for all
    # e.g., "hdfc credit cards", "sbi loans"
    has_bank_name = any(bank.lower() in query_lower for bank in SUPPORTED_BANKS)
    
    is_comprehensive = has_explicit_phrase or (has_bank_name and has_product_plural)
    
    # FIX: COUNT queries need all results, not max_results=15
    is_count_query = any(word in query_lower for word in ['how many', 'count', 'number of'])
    
    # Set appropriate max_results
    if is_count_query:
        max_results = 100  # Get all products for count queries
    elif is_comprehensive:
        max_results = 50  # Get all for comprehensive lists
    else:
        max_results = 15  # Default for focused queries
    
    retrieval_response = retriever.retrieve(user_query, max_results=max_results, chat_history=chat_history)
    results = retrieval_response['results']
    metadata = retrieval_response['metadata']
    
    logging.info(f"Retrieved {len(results)} results from {metadata['sources_searched']}")
    
    # === SMART SUGGESTIONS FOR FAILED COMPARISONS ===
    # Check this BEFORE the early return for no results
    query_lower = user_query.lower().strip()
    is_comparison = any(word in query_lower for word in ['compare', 'vs', 'versus', 'difference between', 'better than'])
    
    if is_comparison and not results:
        # No products found for comparison - suggest similar names
        suggestion_text = "❓ I couldn't find the products you're trying to compare.\n\n"
        suggestion_text += "💡 **Tips for better comparisons:**\n"
        suggestion_text += "1. Use full product names (e.g., 'HDFC Millennia Credit Card')\n"
        suggestion_text += "2. Try: 'List all HDFC credit cards' to see available products\n"
        suggestion_text += "3. Or ask: 'Best credit card for students'\n\n"
        suggestion_text += "**Popular comparisons:**\n"
        suggestion_text += "• HDFC Millennia vs HDFC Regalia Gold\n"
        suggestion_text += "• HDFC Swiggy vs SBI SimplySave\n"
        suggestion_text += "• HDFC Infinia Metal vs SBI Aurum"
        
        return {
            "text": suggestion_text,
            "source": "Comparison Help",
            "data": [],
            "metadata": metadata
        }
    
    # Check if we have any results
    if not results:
        # No results found
        return {
            "text": f"I couldn't find specific information on that. Could you rephrase your question or ask about {get_banks_short()} banking products and services?",
            "source": "No results",
            "data": None,
            "metadata": metadata
        }
    
    # === CHECK FOR GENERAL CHAT (Simple Greetings) ===
    # Handle greetings and non-banking queries with simple fallback
    # IMPORTANT: Only trigger on standalone greetings, not queries containing these words
    query_lower = user_query.lower().strip()
    
    # Check if query is ONLY a greeting (not part of a longer question)
    is_greeting_only = (
        query_lower in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'] or
        query_lower.startswith('hi ') or query_lower.startswith('hello ') or
        query_lower.startswith('hey ')
    )
    
    if is_greeting_only:
        return {
            "text": f"Hello! I'm your Banking Assistant for {get_banks_short()}. I can help you with:\n- {get_categories_display()}\n- Interest Rates, Fees, Eligibility\n- How-to guides and procedures\n\nWhat would you like to know?",
            "source": "Greeting",
            "data": None
        }
    
    # === SMART LISTING DETECTION ===
    # For comprehensive listing queries, bypass LLM and format directly in Python
    # This guarantees ALL products are listed without truncation
    is_comprehensive_list = any(phrase in query_lower for phrase in [
        'all', 'list all', 'give me all', 'show me all', 'explain all',
        'what are all', 'tell me all', 'information on all'
    ])
    
    # Extract product data
    product_results = [r for r in results if r['type'] == 'product']
    
    # CRITICAL: Check if this is a COUNT query BEFORE applying truncation logic
    is_count_query = any(word in query_lower for word in ['how many', 'count', 'number of'])
    
    # Check if this is a RECOMMENDATION query (should use sql_tool's filtering)
    is_recommendation = any(word in query_lower for word in ['best', 'recommend', 'suggest', 'good for', 'suitable'])
    
    # CRITICAL FIX: Force Python formatting for large result sets (>10 products)
    # This prevents LLM truncation regardless of query phrasing
    # BUT skip for COUNT queries (they should return a number, not a list)
    # AND skip for RECOMMENDATION queries (they have their own filtering logic)
    if len(product_results) > 10 and not is_count_query and not is_recommendation:
        is_comprehensive_list = True
        logging.info(f"Forcing Python formatting for {len(product_results)} products to prevent truncation")
    
    if is_comprehensive_list and len(product_results) > 5:
        # === PYTHON FORMATTING for comprehensive lists ===
        # Check if user wants detailed explanation or just a list
        query_lower = user_query.lower()
        wants_details = 'explain' in query_lower or 'detail' in query_lower or 'tell me about' in query_lower
        
        if wants_details:
            # Show full details
            formatted_text = f"Here are ALL {len(product_results)} products with full details:\n\n"
            
            for i, result in enumerate(product_results, 1):
                product = result.get('raw_data', {})
                
                # Parse attributes JSON if it's a string
                attrs = product.get('attributes', {})
                if isinstance(attrs, str):
                    try:
                        import json
                        attrs = json.loads(attrs)
                    except:
                        attrs = {}
                
                # Extract details from attributes
                bank = product.get('bank_name', 'HDFC')  # Default to bank from query
                name = product.get('product_name', 'Unknown')
                category = product.get('category', 'N/A')
                fees = attrs.get('fees', 'N/A')
                features = attrs.get('features', 'N/A')
                eligibility = attrs.get('eligibility', 'N/A')
                interest_rate = attrs.get('interest_rate', 'N/A')
                
                formatted_text += f"{i}. **{name}**\n"
                formatted_text += f"   - Bank: {bank}\n"
                formatted_text += f"   - Fees: {fees}\n"
                formatted_text += f"   - Features: {features}\n"
                formatted_text += f"   - Eligibility: {eligibility}\n"
                if interest_rate != 'N/A':
                    formatted_text += f"   - Interest Rate: {interest_rate}\n"
                formatted_text += "\n"
        else:
            # Just show concise list of names
            formatted_text = f"Here are ALL {len(product_results)} products:\n\n"
            for i, result in enumerate(product_results, 1):
                product = result.get('raw_data', {})
                name = product.get('product_name', 'Unknown')
                formatted_text += f"{i}. {name}\n"
        
        return {
            "text": formatted_text,
            "source": f"Multi-Source ({metadata['sql_count']} products, {metadata['faq_count']} FAQs)",
            "data": [r['raw_data'] for r in product_results],
            "metadata": metadata
        }
    
    # === COMPARISON TABLE FORMATTING ===
    # Check if this is a comparison query
    is_comparison = any(word in query_lower for word in ['compare', 'vs', 'versus', 'difference between', 'better than'])
    
    # Smart Suggestions: If comparison query but found 0-1 products, suggest correct names
    if is_comparison and len(product_results) < 2:
        # Extract keywords from query
        keywords = []
        for word in query_lower.split():
            if word not in ['compare', 'vs', 'versus', 'difference', 'between', 'and', 'the', 'a', 'an', 'card', 'loan']:
                keywords.append(word)
        
        # Search for similar product names
        all_products = [r.get('raw_data', {}) for r in results if r.get('type') == 'product']
        suggestions = []
        
        for keyword in keywords[:3]:  # Check first 3 keywords
            for product in all_products[:20]:  # Check first 20 products
                name = product.get('product_name', '').lower()
                if keyword in name and product.get('product_name') not in suggestions:
                    suggestions.append(product.get('product_name'))
        
        if suggestions:
            suggestion_text = "❓ I couldn't find enough products to compare. Did you mean one of these?\n\n"
            for i, name in enumerate(suggestions[:5], 1):
                suggestion_text += f"{i}. {name}\n"
            suggestion_text += "\n💡 Try: \"Compare " + " vs ".join(suggestions[:2]) + "\""
            
            return {
                "text": suggestion_text,
                "source": "Comparison Suggestions",
                "data": [],
                "metadata": metadata
            }
    
    if is_comparison and 2 <= len(product_results) <= 3:
        # Format as comparison table
        import json
        
        # Extract product data
        products_data = []
        for result in product_results[:3]:  # Max 3 products
            product = result.get('raw_data', {})
            
            # Parse attributes
            attrs = product.get('attributes', {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except:
                    attrs = {}
            
            products_data.append({
                'name': product.get('product_name', 'Unknown'),
                'bank': product.get('bank_name', 'N/A'),
                'fees': attrs.get('fees', 'N/A'),
                'features': attrs.get('features', 'N/A'),
                'eligibility': attrs.get('eligibility', 'N/A'),
                'interest_rate': attrs.get('interest_rate', 'N/A')
            })
        
        # Build comparison table
        table_text = "## Product Comparison\n\n"
        
        # Header row
        table_text += "| Feature | "
        table_text += " | ".join([p['name'] for p in products_data])
        table_text += " |\n"
        
        # Separator row
        table_text += "|" + "---|" * (len(products_data) + 1) + "\n"
        
        # Bank row
        table_text += "| **Bank** | "
        table_text += " | ".join([p['bank'] for p in products_data])
        table_text += " |\n"
        
        # Fees row
        table_text += "| **Annual Fees** | "
        table_text += " | ".join([p['fees'] for p in products_data])
        table_text += " |\n"
        
        # Features row (truncate if too long)
        table_text += "| **Key Features** | "
        table_text += " | ".join([p['features'][:50] + "..." if len(p['features']) > 50 else p['features'] for p in products_data])
        table_text += " |\n"
        
        # Eligibility row
        table_text += "| **Eligibility** | "
        table_text += " | ".join([p['eligibility'] for p in products_data])
        table_text += " |\n"
        
        # Interest rate row (if applicable)
        if any(p['interest_rate'] != 'N/A' for p in products_data):
            table_text += "| **Interest Rate** | "
            table_text += " | ".join([p['interest_rate'] for p in products_data])
            table_text += " |\n"
        
        table_text += "\n---\n"
        table_text += f"💡 **Quick Tip:** Choose based on your spending pattern and income level."
        
        return {
            "text": table_text,
            "source": f"Product Comparison ({len(products_data)} products)",
            "data": [r['raw_data'] for r in product_results],
            "metadata": metadata
        }
    
    # === SYNTHESIZE FROM ALL SOURCES ===
    # Build context from all retrieved results
    # Increase to 20 to handle comprehensive queries like "all SBI credit cards"
    context_text = "\n\n".join([
        f"[Source: {r['source']}]\n{r['content']}" for r in results[:20]
    ])
    
    # Prepare history context
    history_context = ""
    if chat_history and len(chat_history) > 0:
        recent = chat_history[-2:]
        history_context = "\nRecent conversation:\n" + "\n".join([
            f"- {msg['role']}: {msg['content'][:100]}" for msg in recent
        ])
    
    synthesis_prompt = f"""
You are a helpful Banking Assistant for {get_banks_short()} banks.
Your task is to synthesize the following context into a natural, conversational answer.

User Query: "{user_query}"
{history_context}

Retrieved Information from Multiple Sources:
{context_text}

CRITICAL INSTRUCTIONS:

1. **Response Type Detection**:
   - If user asks "how many", "count", "number of" → Provide ONLY a count with brief summary
   - If user asks "all", "list", "explain all", "what are", "show me" → List EVERY SINGLE product
   - If follow-up query says "all", "them", "those" → User wants details about previous query results

2. **Completeness Guarantee**:
   - When listing products, start with: "Here are ALL {metadata.get('sql_count', 0)} [product type]:"
   - DO NOT truncate or skip items - list ALL {len(results[:20])} items retrieved
   - Use numbered lists (1., 2., 3., ...) to ensure you don't skip any
   
3. **Formatting**:
   - For COUNT queries: "SBI offers 16 credit cards: [list names briefly]"
   - For DETAILED listings: Show each product with fees, features, eligibility
   - Use clear structure and bullet points

4. **Context Awareness**:
   - If user says "explain all" or "list those" after a count query, expand with full details
   - Reference previous conversation context to understand what "all" or "those" refers to

5. **Accuracy**:
   - Use ONLY information from the retrieved data above
   - If info is missing for a product (N/A), state it clearly
   - Do NOT make up information

If the context doesn't contain the answer, say "I don't have that specific information in my database."
    """
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": synthesis_prompt},
            {"role": "user", "content": user_query}
        ],
        model=LLM_MODEL,
        temperature=0.3
    )
    
    # Extract product data for table display
    product_data = [r['raw_data'] for r in results if r['type'] == 'product']
    
    return {
        "text": response.choices[0].message.content,
        "source": f"Multi-Source ({metadata['sql_count']} products, {metadata['faq_count']} FAQs)",
        "data": product_data[:20] if product_data else None,
        "metadata": metadata
    }

if __name__ == "__main__":
    # Test CLI
    logging.basicConfig(level=logging.INFO)
    print("🤖 Agent CLI (Type 'quit' to exit)")
    history = []
    while True:
        q = input("\nYou: ")
        if q.lower() == "quit": break
        
        # Add user msg to history
        history.append({"role": "user", "content": q})
        
        response_obj = process_query(q, chat_history=history)
        
        # Handle dict response
        if isinstance(response_obj, dict):
            ans_text = response_obj.get("text", "")
            source = response_obj.get("source", "")
            print(f"Agent ({source}): {ans_text}")
        else:
            ans_text = str(response_obj)
            print(f"Agent: {ans_text}")
        
        # Add assistant msg to history
        history.append({"role": "assistant", "content": ans_text})
