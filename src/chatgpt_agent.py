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

def chatgpt_query(user_query: str, chat_history: Optional[List[Dict]] = None, clarification_mode: bool = False) -> Dict[str, Any]:
    """
    ChatGPT-style conversational query handler.
    
    Uses RAG to retrieve relevant context and lets LLM handle response naturally
    without rigid query classification.
    
    Args:
        user_query: User's question
        chat_history: Full conversation history
        clarification_mode: If True, focus on asking clarifying questions for vague queries
        
    Returns:
        Response dict with text, source, data, metadata
    """
    logging.info(f"[ChatGPT Mode] Processing: {user_query} (clarification={clarification_mode})")
    
    # 1. Retrieve relevant context (no query classification needed)
    # For clarification mode, reduce results to keep response focused on guidance
    max_results = 15 if clarification_mode else 30
    retrieval_result = retriever.retrieve(user_query, max_results=max_results, chat_history=chat_history)
    results = retrieval_result['results']
    metadata = retrieval_result['metadata']
    
    # 2. Format retrieved documents as context
    context_docs = []
    product_data = []
    
    # Get available banks from metadata
    from src.config import SUPPORTED_BANKS
    banks_text = ", ".join(SUPPORTED_BANKS[:-1]) + f", and {SUPPORTED_BANKS[-1]}" if len(SUPPORTED_BANKS) > 1 else SUPPORTED_BANKS[0]
    
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
            
            # Format product info
            context_docs.append(f"""
Product: {product.get('product_name', 'Unknown')}
Bank: {product.get('bank_name', 'N/A')}
Category: {product.get('category', 'N/A')}
Fees: {attrs.get('fees', 'N/A')}
Features: {attrs.get('features', 'N/A')[:150]}...
Eligibility: {attrs.get('eligibility', 'N/A')[:100]}...
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
        system_prompt = f"""You are a helpful banking assistant for {banks_text}.

**Retrieved Context from Database:**
{context_text}

**Instructions:**
- Answer questions naturally and conversationally
- Use ONLY the retrieved context above - do not make up information
- If asked for counts, count the products in the context
- If asked to list products, list them clearly with numbers and key details
- If comparing products, create clear comparison tables
- If recommending, analyze the options and explain your reasoning
- Be friendly, helpful, and accurate
- Maintain conversation context from chat history
- If information is missing, say so honestly and suggest asking differently

**Important:** The context above shows relevant products from our database. Use it as your source of truth.
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
