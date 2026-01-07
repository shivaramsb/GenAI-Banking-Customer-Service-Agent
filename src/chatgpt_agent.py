"""
ChatGPT-style Conversational Agent

Provides natural, conversational responses using RAG without rigid query classification.
Used for general questions, follow-ups, and exploratory conversations.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from openai import OpenAI
from src.config import OPENAI_API_KEY, LLM_MODEL, get_banks_short
from src.multi_retriever import MultiSourceRetriever

client = OpenAI(api_key=OPENAI_API_KEY)
retriever = MultiSourceRetriever()

def chatgpt_query(user_query: str, chat_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    ChatGPT-style conversational query handler.
    
    Uses RAG to retrieve relevant context and lets LLM handle response naturally
    without rigid query classification.
    
    Args:
        user_query: User's question
        chat_history: Full conversation history
        
    Returns:
        Response dict with text, source, data, metadata
    """
    logging.info(f"[ChatGPT Mode] Processing: {user_query}")
    
    # 1. Retrieve relevant context (no query classification needed)
    retrieval_result = retriever.retrieve(user_query, max_results=30, chat_history=chat_history)
    results = retrieval_result['results']
    metadata = retrieval_result['metadata']
    
    # 2. Format retrieved documents as context
    context_docs = []
    product_data = []
    
    for result in results[:20]:  # Limit to prevent token overflow
        if result['type'] == 'product':
            product = result['raw_data']
            product_data.append(product)
            
            # Parse attributes
            attrs = product.get('attributes', {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except:
                    attrs = {}
            
            # Format product info
            context_docs.append(f"""
Product: {product.get('product_name', 'Unknown')}
Bank: {product.get('bank_name', 'N/A')}
Category: {product.get('category', 'N/A')}
Fees: {attrs.get('fees', 'N/A')}
Features: {attrs.get('features', 'N/A')}
Eligibility: {attrs.get('eligibility', 'N/A')}
""".strip())
        
        elif result['type'] == 'faq':
            faq = result['raw_data']
            context_docs.append(f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}")
    
    context_text = "\n\n".join(context_docs)
    
    # 3. Build conversation messages
    messages = []
    
    # System message with context and instructions
    system_prompt = f"""You are a helpful banking assistant for {get_banks_short()} banks.

**Retrieved Context from Database:**
{context_text}

**Instructions:**
- Answer questions naturally and conversationally
- Use ONLY the retrieved context above - do not make up information
- If asked for counts, count the products in the context
- If asked to list products, list them clearly with numbers
- If comparing products, create clear comparison tables
- If recommending, analyze the options and explain your reasoning
- Be friendly, helpful, and accurate
- Maintain conversation context from chat history
- If information is missing, say so honestly

**Important:** The context above shows ALL relevant products from our database. Use it as your sole source of truth.
"""
    
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
    
    # 4. Get LLM response
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,  # More conversational than structured mode
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content
        
        return {
            "text": response_text,
            "source": f"ChatGPT-style ({metadata.get('sql_count', 0)} products, {metadata.get('faq_count', 0)} FAQs)",
            "data": product_data if product_data else None,
            "metadata": metadata
        }
        
    except Exception as e:
        logging.error(f"ChatGPT query error: {e}")
        return {
            "text": f"Sorry, I encountered an error processing your query: {str(e)}",
            "source": "Error",
            "data": None,
            "metadata": {}
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
