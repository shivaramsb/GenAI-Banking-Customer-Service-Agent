"""
ChatGPT-style Conversational Agent

Provides natural, conversational responses using RAG without rigid query classification.
Used for general questions, follow-ups, and exploratory conversations.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from openai import OpenAI
from src.config import OPENAI_API_KEY, LLM_MODEL, get_banks_short, SUPPORTED_BANKS
from src.multi_retriever import MultiSourceRetriever

# Module-level configuration
MAX_CONTEXT_RESULTS = 15  # Configurable: max results to include in context
MAX_RETRIEVAL_RESULTS = 30  # Configurable: max results to retrieve

client = OpenAI(api_key=OPENAI_API_KEY)
retriever = MultiSourceRetriever()

def chatgpt_query(user_query: str, chat_history: Optional[List[Dict]] = None, clarification_mode: bool = False, intent: Optional[str] = None, suppress_count: bool = False) -> Dict[str, Any]:
    """
    ChatGPT-style conversational query handler.
    
    Uses RAG to retrieve relevant context and lets LLM handle response naturally
    without rigid query classification.
    
    Args:
        user_query: User's question
        chat_history: Full conversation history
        clarification_mode: If True, focus on asking clarifying questions for vague queries
        intent: The detected intent (FAQ, RECOMMEND, COMPARE, etc.) for metadata
        suppress_count: If True, instruct LLM NOT to count products (used in multi-op when COUNT already handled)
        
    Returns:
        Response dict with text, source, data, metadata
    """
    logging.info(f"[ChatGPT Mode] Processing: {user_query} (clarification={clarification_mode}, suppress_count={suppress_count})")
    
    # 1. Retrieve relevant context (no query classification needed)
    # For clarification mode, reduce results to keep response focused on guidance
    max_results = MAX_CONTEXT_RESULTS if clarification_mode else MAX_RETRIEVAL_RESULTS
    retrieval_result = retriever.retrieve(user_query, max_results=max_results, chat_history=chat_history)
    results = retrieval_result['results']
    metadata = retrieval_result['metadata']
    
    # Add intent to metadata for HistoryStateManager
    if intent:
        metadata['intent'] = intent
    
    # 2. Format retrieved documents as context
    context_docs = []
    product_data = []
    
    # Get available banks text using config helper
    banks_text = get_banks_short()
    
    # Extract product categories from results for clarification
    categories_found = set()
    
    for result in results[:20]:  # Limit to prevent token overflow
        if result['type'] == 'product':
            product = result['raw_data']
            product_data.append(product)
            categories_found.add(product.get('category', 'Unknown'))
            
            # Parse attributes
            attrs = product.get('attributes', {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except:
                    attrs = {}
            
            # Format product info - safely convert to string before slicing
            fees = str(attrs.get('fees', 'N/A'))
            features = str(attrs.get('features', 'N/A'))[:150]
            eligibility = str(attrs.get('eligibility', 'N/A'))[:100]
            
            context_docs.append(f"""
Product: {product.get('product_name', 'Unknown')}
Bank: {product.get('bank_name', 'N/A')}
Category: {product.get('category', 'N/A')}
Fees: {fees}
Features: {features}...
Eligibility: {eligibility}...
""".strip())
        
        elif result['type'] == 'faq':
            faq = result['raw_data']
            context_docs.append(f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')[:150]}...")
    
    context_text = "\n\n".join(context_docs[:15])  # Limit context for clarity
    
    # 3. Build conversation messages
    messages = []
    
    # System message with context and instructions
    if clarification_mode:
        # Special prompt for vague queries - focus on clarification
        system_prompt = f"""You are a helpful banking assistant for {banks_text}.

The user asked a vague question: "{user_query}"

**Your goal:** Help them ask a better question by providing intelligent guidance.

**Available information:**
- We support {len(SUPPORTED_BANKS)} banks: {banks_text}
- We found these relevant categories: {', '.join(sorted(categories_found)) if categories_found else 'multiple product types'}
- Retrieved {len(results)} relevant items from our database

**Instructions:**
1. Acknowledge what they're looking for
2. Mention the options we have available (banks, categories)
3. Ask 2-3 smart clarifying questions to guide them:
   - Which bank do they prefer?
   - What specific type/category?
   - Any particular needs or preferences?
4. Be friendly, encouraging, and helpful

**Format your response as:**
- Brief acknowledgment
- Quick overview of options
- 2-3 specific clarifying questions

DO NOT list all products or provide example queries. Just ask helpful questions.
"""
    else:
        # Normal conversational mode
        count_instruction = "" if suppress_count else "- If asked for counts, count the products in the context\n"
        
        system_prompt = f"""You are a helpful banking assistant for {banks_text}.

**Retrieved Context from Database:**
{context_text}

**Instructions:**
- Answer questions naturally and conversationally
- Use ONLY the retrieved context above - do not make up information
{count_instruction}- If asked to list products, list them clearly with numbers and key details
- If comparing products, create clear comparison tables
- If recommending, analyze the options and explain your reasoning
- Be friendly, helpful, and accurate
- Maintain conversation context from chat history
- If information is missing, say so honestly and suggest asking differently

**Important:** The context above shows relevant products from our database. Use it as your source of truth.
"""
        if suppress_count:
            system_prompt += "\n**Note:** Do NOT count or mention the number of products - focus only on answering the procedural/informational aspects of the question."
    
    messages.append({"role": "system", "content": system_prompt})
    
    # Add chat history (full context for ChatGPT-style)
    if chat_history:
        # Include all history for full context awareness
        for msg in chat_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
    
    # Add current query
    messages.append({"role": "user", "content": user_query})
    
    # 4. Get LLM response with robust error handling
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,  # More conversational than structured mode
            max_tokens=2000,
            timeout=30  # 30 second timeout
        )
        
        response_text = response.choices[0].message.content
        
        # Extract structured data for follow-ups
        if intent == 'RECOMMEND':
            # Try to extract the recommended product name
            import re
            # Look for bolded product names
            match = re.search(r'\*\*([A-Za-z0-9\s\-\.]+?)\*\*', response_text)
            if match:
                product_name = match.group(1).strip()
                # Filter out common non-product bold text
                if len(product_name) > 5 and not product_name.lower().startswith(('note', 'consider', 'important', 'best', 'key')):
                    metadata['recommended_product'] = product_name
                    logging.info(f"[RECOMMEND] Extracted product: {product_name}")
        
        elif intent == 'COMPARE':
            # Try to extract compared product names
            import re
            # Look for product names in comparison context
            # Pattern: "Product1 vs Product2" or "Product1 and Product2"
            matches = re.findall(r'\b([A-Z][A-Za-z0-9\s]{3,50}?(?:Card|Loan|Account))\b', response_text)
            if matches and len(matches) >= 2:
                # Take first 2-3 unique products
                compared = list(dict.fromkeys(matches))[:3]
                metadata['compared_products'] = compared
                logging.info(f"[COMPARE] Extracted products: {compared}")
        
        return {
            "text": response_text,
            "source": f"ChatGPT-style ({metadata.get('sql_count', 0)} products, {metadata.get('faq_count', 0)} FAQs)",
            "data": product_data if product_data else None,
            "metadata": metadata
        }
        
    except Exception as e:
        error_str = str(e).lower()
        logging.error(f"ChatGPT query error: {e}")
        
        # Provide helpful fallback based on error type
        if 'rate limit' in error_str or 'rate_limit' in error_str:
            error_msg = "⚠️ I'm receiving too many requests right now. Please try again in a few seconds."
        elif 'connection' in error_str or 'timeout' in error_str:
            error_msg = "⚠️ I'm having trouble connecting to my AI service. Please try again."
        elif 'api key' in error_str or 'authentication' in error_str:
            error_msg = "⚠️ There's a configuration issue. Please contact support."
        else:
            # Provide context-based fallback if we have retrieved data
            if product_data:
                product_names = [p.get('product_name', '') for p in product_data[:5]]
                error_msg = f"I found some relevant products but couldn't generate a detailed response:\n\n"
                error_msg += "\n".join([f"• {name}" for name in product_names if name])
                error_msg += "\n\n_Please try rephrasing your question._"
            else:
                error_msg = "⚠️ Sorry, I couldn't process your query. Please try rephrasing or ask something else."
        
        return {
            "text": error_msg,
            "source": "Fallback",
            "data": product_data if product_data else None,
            "metadata": {"error": str(e)}
        }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    test_queries = [
        "Tell me about HDFC credit cards",
        "Which one would you recommend for students?",
        "What are the main differences between them?"
    ]
    
    history = []
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"User: {query}")
        response = chatgpt_query(query, chat_history=history)
        print(f"Assistant: {response['text']}")
        
        # Update history
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response['text']})
