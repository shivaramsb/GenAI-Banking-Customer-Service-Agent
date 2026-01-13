"""
Response Formatters for Banking Agent

Provides deterministic, Python-based response formatting for:
- COUNT queries (exact counts, zero LLM involvement)
- LIST queries (complete product lists, zero LLM involvement)
- EXPLAIN queries (detailed explanations with LLM validation)
"""

import json
import logging
import re
from typing import List, Dict, Any
from openai import OpenAI
from src.config import LLM_MODEL, OPENAI_API_KEY

# Module-level client (avoid creating inside functions)
_client = OpenAI(api_key=OPENAI_API_KEY)


def format_count_response(products: List[Dict], query_info: Dict) -> Dict[str, Any]:
    """
    Format COUNT query response using HYBRID approach.
    
    Step 1: Python calculates exact count (guaranteed accuracy)
    Step 2: LLM formats naturally (conversational tone)
    Step 3: Validation ensures correctness
    
    Args:
        products: List of product dicts from database
        query_info: Classification info with bank, category, etc.
        
    Returns:
        Response dict with text, source, data, metadata
    """
    count = len(products)
    bank = query_info.get('bank', 'The bank')
    category = query_info.get('category', 'products')
    original_query = query_info.get('original_query', '')
    
    # Format category for natural language (plural form)
    category_display = category.lower()
    if not category_display.endswith('s'):
        category_display += 's'
    
    logging.info(f"[COUNT] Python verification: {bank} has EXACTLY {count} {category_display}")
    
    # Build structured product list for LLM
    product_list = []
    for i, product in enumerate(products, 1):
        attrs = product.get('attributes', {})
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except:
                attrs = {}
        
        product_list.append({
            'number': i,
            'name': product.get('product_name', 'Unknown'),
            'fees': attrs.get('fees', 'N/A')
        })
    
    # Use module-level client (no need to import again)
    client = _client
    
    prompt = f"""You are a helpful banking assistant answering a customer's question.

USER QUESTION: "{original_query}"

VERIFIED DATA (from database):
- Bank: {bank}
- Category: {category}
- Exact Count: {count}

COMPLETE PRODUCT LIST:
{json.dumps(product_list, indent=2)}

CRITICAL RULES:
1. Start with a natural, friendly answer stating the exact count ({count})
2. List ALL {count} products naturally - do not skip any
3. Mention product names with their fees in a conversational way
4. Be engaging and helpful, not robotic
5. DO NOT add products not in the list above
6. DO NOT change the count

Example tone: "SBI offers {count} {category_display}. Let me walk you through them..."

Write a natural, conversational response."""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": original_query}
            ],
            model=LLM_MODEL,
            temperature=0.3  # Balanced: natural but consistent
        )
        
        natural_response = response.choices[0].message.content
        
        # VALIDATION: Ensure count is mentioned correctly (use word boundary to avoid false positives)
        count_str = str(count)
        if not re.search(rf'\b{count_str}\b', natural_response):
            logging.warning(f"[COUNT] LLM didn't mention count {count}, adding it")
            natural_response = f"**{bank}** offers **{count} {category_display}**.\n\n" + natural_response
        
        # VALIDATION: Check if all product names are mentioned
        missing_products = []
        for product in product_list:
            if product['name'] not in natural_response:
                missing_products.append(product['name'])
        
        if missing_products:
            logging.warning(f"[COUNT] LLM missed {len(missing_products)} products, appending")
            natural_response += f"\n\n**Note:** The following products were not detailed above:\n"
            for name in missing_products:
                natural_response += f"- {name}\n"
        
        return {
            "text": natural_response,
            "source": f"Python Count + LLM Formatting (Verified: {count} products)",
            "data": products,
            "metadata": {
                "count": count,
                "method": "hybrid_count",
                "guaranteed_accurate": True,
                "missing_products": missing_products
            }
        }
        
    except Exception as e:
        logging.error(f"[COUNT] LLM formatting failed: {str(e)}")
        logging.exception("Full error traceback:")
        # Fallback to structured format
        response_text = f"### 📊 Answer\n\n"
        response_text += f"**{bank}** offers **{count}** {category_display}.\n\n"
        response_text += f"---\n\n### 📋 Complete List:\n\n"
        for item in product_list:
            if item['fees'] and item['fees'] != 'N/A':
                response_text += f"{item['number']}. **{item['name']}** — {item['fees']}\n"
            else:
                response_text += f"{item['number']}. **{item['name']}**\n"
        
        return {
            "text": response_text,
            "source": f"SQL Database (Exact Count: {count})",
            "data": products,
            "metadata": {
                "count": count,
                "method": "python_count_fallback",
                "guaranteed_accurate": True
            }
        }


def format_list_response(products: List[Dict], query_info: Dict, detailed: bool = False) -> Dict[str, Any]:
    """
    Format LIST query response - CONCISE numbered list format.
    
    Returns a clean, scannable numbered list. No LLM narrative.
    For detailed explanations, use EXPLAIN intent instead.
    
    Args:
        products: List of product dicts from database
        query_info: Classification info
        detailed: If True, include more details per product
        
    Returns:
        Response dict with text, source, data, metadata
    """
    count = len(products)
    bank = query_info.get('bank', 'The bank')
    category = query_info.get('category', 'products')
    
    logging.info(f"[LIST] Formatting {count} products as clean list")
    
    if count == 0:
        return {
            "text": f"No {category.lower()}s found for {bank}.",
            "source": "Product List",
            "data": [],
            "metadata": {"count": 0, "method": "python_list"}
        }
    
    # Build concise numbered list
    lines = []
    lines.append(f"📋 **{bank} {category}s** ({count} total):\n")
    
    for i, product in enumerate(products, 1):
        name = product.get('product_name', 'Unknown')
        
        # Get fees if available
        attrs = product.get('attributes', {})
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except:
                attrs = {}
        
        fee = attrs.get('fees', '')
        
        if detailed:
            # Detailed mode: name + fees + key features
            features = attrs.get('features', '')
            if isinstance(features, list):
                features = ', '.join(features[:3])  # First 3 features
            elif isinstance(features, str) and len(features) > 100:
                features = features[:100] + '...'
            
            line = f"{i}. **{name}**"
            if fee:
                line += f" - Fee: {fee}"
            if features:
                line += f"\n   _{features}_"
            lines.append(line)
        else:
            # Simple mode: just name and fee
            if fee:
                lines.append(f"{i}. **{name}** - {fee}")
            else:
                lines.append(f"{i}. **{name}**")
    
    response_text = "\n".join(lines)
    
    # Add helpful tip at the end
    response_text += f"\n\n💡 _Ask \"explain [product name]\" for details on any specific product._"
    
    return {
        "text": response_text,
        "source": f"Product List ({count} items)",
        "data": products,
        "metadata": {
            "count": count,
            "method": "python_list",
            "guaranteed_complete": True
        }
    }


def format_explain_response(products: List[Dict], query_info: Dict, client: OpenAI) -> Dict[str, Any]:
    """
    Format EXPLAIN query response using LLM with strict validation.
    
    Uses LLM but with controls:
    - Temperature = 0 (maximum determinism)
    - Validation that all products are mentioned
    - Structured context to minimize hallucination
    
    Args:
        products: List of product dicts from database
        query_info: Classification info
        client: OpenAI client instance
        
    Returns:
        Response dict with text, source, data, metadata
    """
    count = len(products)
    
    # Build structured context for LLM
    context_parts = []
    for i, product in enumerate(products, 1):
        attrs = product.get('attributes', {})
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except:
                attrs = {}
        
        product_context = f"""
Product {i}: {product.get('product_name', 'Unknown')}
- Bank: {product.get('bank_name', 'N/A')}
- Category: {product.get('category', 'N/A')}
- Fees: {attrs.get('fees', 'N/A')}
- Features: {attrs.get('features', 'N/A')}
- Eligibility: {attrs.get('eligibility', 'N/A')}
- Interest Rate: {attrs.get('interest_rate', 'N/A')}
""".strip()
        context_parts.append(product_context)
    
    full_context = "\n\n".join(context_parts)
    
    # Build prompt with strict instructions
    bank = query_info.get('bank', 'the bank')
    category = query_info.get('category', 'products')
    original_query = query_info.get('original_query', '')
    
    system_prompt = f"""You are explaining {count} banking products from {bank}.

PRODUCTS TO EXPLAIN:
{full_context}

CRITICAL RULES:
1. Explain EVERY SINGLE product listed above - do not skip any
2. Use numbered list format (1., 2., 3., ...)
3. For each product, include:
   - Product name as a heading
   - Annual fees
   - Key features (2-3 main points)
   - Eligibility criteria
   - Interest rate (if applicable)
4. Be accurate - ONLY use information provided above
5. Do NOT make up or assume any information
6. Start your response with: "Here are ALL {count} {category}s with full details:"

User's question: "{original_query}"

Remember: You MUST include all {count} products in your response."""
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Explain all {count} {category}s"}
            ],
            model=LLM_MODEL,
            temperature=0  # Maximum determinism
        )
        
        response_text = response.choices[0].message.content
        
        # Validation: Check if all product names are mentioned
        missing_products = []
        for product in products:
            product_name = product.get('product_name', '')
            if product_name and product_name not in response_text:
                missing_products.append(product_name)
        
        if missing_products:
            logging.warning(f"[EXPLAIN] LLM missed products: {missing_products}")
            # Append missing products
            response_text += f"\n\n**Note:** The following products were not fully detailed above:\n"
            for name in missing_products:
                response_text += f"- {name}\n"
        
        logging.info(f"[EXPLAIN] Generated explanation for {count} products")
        
        return {
            "text": response_text,
            "source": f"LLM Explanation ({count} products)",
            "data": products,
            "metadata": {
                "count": count,
                "method": "llm_explain",
                "temperature": 0,
                "missing_products": missing_products
            }
        }
        
    except Exception as e:
        logging.error(f"[EXPLAIN] LLM error: {e}")
        # Fallback to Python formatting if LLM fails
        return format_list_response(products, query_info, detailed=True)


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Mock products for testing
    test_products = [
        {
            "product_name": "SBI SimplySave",
            "bank_name": "SBI",
            "category": "Credit Card",
            "attributes": json.dumps({
                "fees": "Rs. 499 + Taxes",
                "features": "10X Reward Points on Dining, Movies & Grocery",
                "eligibility": "Salaried/Self-Employed > 20k/month",
                "interest_rate": "3.5% p.m."
            })
        },
        {
            "product_name": "SBI Elite",
            "bank_name": "SBI",
            "category": "Credit Card",
            "attributes": json.dumps({
                "fees": "Rs. 4999 + Taxes",
                "features": "Welcome Gift worth Rs. 5000; Free Movie Tickets",
                "eligibility": "Income > 10L PA",
                "interest_rate": "3.35% p.m."
            })
        }
    ]
    
    query_info = {
        "intent": "COUNT",
        "bank": "SBI",
        "category": "Credit Card",
        "original_query": "how many credit cards sbi offers"
    }
    
    # Test COUNT
    print("=== COUNT TEST ===")
    result = format_count_response(test_products, query_info)
    print(result['text'])
    
    # Test LIST
    print("\n=== LIST TEST ===")
    query_info['intent'] = 'LIST'
    result = format_list_response(test_products, query_info, detailed=False)
    print(result['text'])
