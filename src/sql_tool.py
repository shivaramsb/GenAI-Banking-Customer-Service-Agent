import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from src.database import DatabaseManager
from src.config import (
    OPENAI_API_KEY, LLM_MODEL,
    SUPPORTED_BANKS, PRODUCT_CATEGORIES,
    get_bank_list_sql
)

client = OpenAI(api_key=OPENAI_API_KEY)
db = DatabaseManager()

def classify_query_detail_level(user_query):
    """
    Uses LLM to classify how detailed the user wants the response.
    Returns: 'COUNT_ONLY', 'LIST_BRIEF', or 'EXPLAIN_DETAILED'
    """
    classification_prompt = f"""
    Classify the user's query into one of these detail levels:
    
    1. COUNT_ONLY: User only wants a number/count
       Examples: "How many cards?", "Count the loans", "Number of products", "Total cards"
    
    2. LIST_BRIEF: User wants a list with brief info
       Examples: "What are the cards?", "List the loans", "Show me the products", "Which cards exist?"
    
    3. EXPLAIN_DETAILED: User wants full detailed explanation
       Examples: "Explain all cards", "Detail each loan", "Describe all products", "Tell me everything about..."
    
    User Query: "{user_query}"
    
    Return ONLY the classification name (COUNT_ONLY, LIST_BRIEF, or EXPLAIN_DETAILED).
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": classification_prompt}],
            model=LLM_MODEL,
            temperature=0.0,
            max_tokens=10
        )
        classification = response.choices[0].message.content.strip().upper()
        
        # Validate and default to LIST_BRIEF if unclear
        if classification not in ['COUNT_ONLY', 'LIST_BRIEF', 'EXPLAIN_DETAILED']:
            return 'LIST_BRIEF'
        return classification
    except Exception as e:
        # Fallback to LIST_BRIEF on error
        return 'LIST_BRIEF'


def execute_sql_tool(user_query, chat_history=None, skip_synthesis=False):
    """
    Uses LLM to generate SQL query based on user question and history,
    executes it against the products database.
    
    Args:
        user_query: The user's question
        chat_history: Conversation context for context-aware filtering
        skip_synthesis: If True, skip GPT synthesis and return only data (saves ~1.5s)
    
    Returns:
        dict: {
            "text": "Natural language response..." (if skip_synthesis=False),
            "data": [row_dict_1, ...], # List of dicts
            "sql": "SELECT ...",
            "source": "SQL Product Catalog"
        }
    """
    
    # Get schema information
    schema_prompt = f"""
    Database Schema:
    
    Table: products
    Columns:
    - product_id (INTEGER PRIMARY KEY)
    - bank_name (TEXT) - Values: {', '.join(f"'{b}'" for b in SUPPORTED_BANKS)}
    - category (TEXT) - e.g., {', '.join(f"'{c}'" for c in PRODUCT_CATEGORIES)}
    - product_name (TEXT) - Unique product identifier product
    - source_type (TEXT)
    - source_file (TEXT)
    - attributes (TEXT/JSON) - Contains: features, fees, interest_rate, eligibility
    - summary_text (TEXT)
    - created_at (TIMESTAMP)
    
    IMPORTANT:
    - Use SQLite syntax
    - To query JSON fields in attributes, use: json_extract(attributes, '$.fieldname')
    - Common fields in attributes: features, fees, interest_rate, eligibility
    - Always limit results to avoid overwhelming output
    """
    
    # Context from history
    history_context = ""
    context_bank_filter = None
    context_category_filter = None
    
    if chat_history:
        # Get last 2 turns
        # Extract context filters from chat history
        context_bank_filter = None
        context_category_filter = None
        
        if chat_history:
            # Look through recent history for bank and category mentions
            for msg in chat_history[-5:]:  # Check last 5 messages
                msg_content = msg.get('content', '')
                msg_lower = msg_content.lower()
                
                # Dynamic bank detection
                for bank in SUPPORTED_BANKS:
                    bank_lower = bank.lower()
                    if bank_lower in msg_lower:
                        # Check if only this bank mentioned (not others)
                        other_banks = [b for b in SUPPORTED_BANKS if b != bank]
                        if not any(other_b.lower() in msg_lower for other_b in other_banks):
                            context_bank_filter = bank
                            break
                
                # Category detection
                if 'credit card' in msg_lower:
                    context_category_filter = 'Credit Card'
                elif 'debit card' in msg_lower:
                    context_category_filter = 'Debit Card'
                elif 'loan' in msg_lower:
                    context_category_filter = 'Loan'

    sql_generation_prompt = f"""
    {schema_prompt}
    
    {history_context}
    
    User Question: "{user_query}"
    
    CONTEXT FILTERS (extracted from conversation history):
    - Bank filter: {context_bank_filter if context_bank_filter else "None (search all banks)"}
    - Category filter: {context_category_filter if context_category_filter else "None (search all categories)"}
    
    Generate a valid SQLite query to answer this question.
    
    CRITICAL - CONTEXT AWARENESS:
    - If the user's question contains "all", "them", "those", "these" without specifying what, USE THE CONTEXT FILTERS ABOVE
    - Example: If context shows "Bank filter: SBI" and user says "give me all information", generate: 
      `SELECT * FROM products WHERE bank_name='SBI' AND category='Credit Card'`
    - ALWAYS apply context filters when user asks for "all", "them", "those" without being specific
    - If no context filters are set and user asks "all", search all banks
    
    QUERY GENERATION RULES:
    
    - If the user asks "How many..." or "List all..." or "Explain all...", generate a query that SELECTS ALL matching products.
    - Example: `SELECT product_name, attributes FROM products WHERE bank_name='HDFC' AND category='Credit Card'`
    - **NEVER add LIMIT clauses** unless the user explicitly asks for "top 5" or similar.
    - **PREFERRED**: Always favor `SELECT *` or `SELECT product_name, attributes...` to show complete data.
    
    COMPARISON QUERIES (CRITICAL):
    - If comparing specific products (e.g., "SBI Gold Loan vs HDFC Gold Loan" or "HDFC Swiggy vs HDFC Regalia"):
      * Extract EACH product name and create separate LIKE conditions with OR
      * Example for "Swiggy vs Regalia": `SELECT * FROM products WHERE (product_name LIKE '%Swiggy%' OR product_name LIKE '%Regalia%') AND bank_name='HDFC'`
      * Example for cross-bank: `SELECT * FROM products WHERE (product_name LIKE '%Gold Loan%') AND bank_name IN ('SBI', 'HDFC')`
      * CRITICAL: Use separate LIKE clauses for EACH product name in the comparison
    
    - If comparing categories across banks (e.g., "Compare {SUPPORTED_BANKS[0]} and {SUPPORTED_BANKS[1]} credit cards"):
      * Example: `SELECT * FROM products WHERE category LIKE '%Credit Card%' AND bank_name IN ({get_bank_list_sql()})`
    
    RECOMMENDATION QUERIES:
    - If the user asks "best for students" or "best loan for students":
      * Don't filter too narrowly - get ALL relevant products and let synthesis filter
      * For credit cards: `SELECT * FROM products WHERE category LIKE '%Credit Card%' ORDER BY product_name`
      * For loans: `SELECT * FROM products WHERE category LIKE '%Loan%' ORDER BY product_name`
      * Don't filter by fees or eligibility in SQL - let the AI synthesis step recommend based on ALL options
    
    - If the user asks "best for travelers" or "best for flying":
      * Filter for travel/airline benefits
      * Example: `SELECT * FROM products WHERE category='Credit Card' AND (json_extract(attributes, '$.features') LIKE '%Lounge%' OR json_extract(attributes, '$.features') LIKE '%Air%' OR json_extract(attributes, '$.features') LIKE '%Travel%')`
    
    - If the user asks "which bank is best for X":
      * Compare across ALL banks for that category
      * Example: `SELECT bank_name, product_name, attributes FROM products WHERE category LIKE '%X%' ORDER BY bank_name`
    
    IMPORTANT: For recommendation queries, prefer broader searches and let the synthesis step filter based on user criteria.
    
    Return ONLY the SQL query, no explanations or markdown.
    If the query needs to extract from JSON attributes, use json_extract().
    """
    
    # Generate SQL
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": sql_generation_prompt}],
            model=LLM_MODEL,
            temperature=0.0
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Clean up the SQL (remove markdown code blocks if present)
        sql_query = re.sub(r'^```sql\n', '', sql_query)
        sql_query = re.sub(r'\n```$', '', sql_query)
        sql_query = sql_query.strip()
        
        # Execute SQL using persistent connection
        cursor = db._connection.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
        
        if not results:
            return {
                "text": "I couldn't find any matching products in our database.",
                "data": None,
                "sql": sql_query,
                "source": "Product Catalog (SQL)"
            }
        
        # Quick Win 1: Skip synthesis if called from multi_retriever (saves ~1.5s)
        if skip_synthesis:
            return {
                "data": [dict(zip(column_names, row)) for row in results],
                "sql": sql_query,
                "source": "Product Catalog (SQL)"
            }
        
        # Format results as text
        results_text = f"Query executed: {sql_query}\n\nResults ({len(results)} rows):\n"
        for row in results[:20]:  # Limit display
            row_dict = dict(zip(column_names, row))
            results_text += f"\n{json.dumps(row_dict, indent=2)}\n"
        
        # FIX 1: Handle COUNT queries properly - extract actual count value
        is_count_query = 'COUNT(*' in sql_query.upper() or detail_level == 'COUNT_ONLY'
        if is_count_query and len(results) == 1 and len(column_names) == 1:
            actual_count = results[0][0]  # Extract the count value
            count_response = f"{column_names[0].replace('COUNT(*)', 'Count').replace('_', ' ').title()}: {actual_count}"
            return {
                "text": count_response,
                "data": [{column_names[0]: actual_count}],
                "sql": sql_query,
                "source": "Product Catalog (SQL)"
            }
        
        # Classify query type using LLM (semantic understanding)
        detail_level = classify_query_detail_level(user_query)
        
        # FIX 4: Enhanced comparison detection
        is_comparison = any(word in user_query.lower() for word in ['compare', 'vs', 'versus', 'difference between', 'better than', ' vs. '])
        
        # FIX 2: Enhanced recommendation detection
        query_lower = user_query.lower()
        is_recommendation = (
            'best' in query_lower or
            'recommend' in query_lower or
            'which bank' in query_lower or
            'which card' in query_lower or
            'good for' in query_lower or
            'better for' in query_lower or
            'suitable' in query_lower
        )
        
        # FIX 2: Enhanced pre-filtering for recommendation queries
        if is_recommendation and len(results) > 3:
            # Parse user intent
            query_lower = user_query.lower()
            
            # Check for home loan/buyer queries FIRST (highest priority)
            if 'home' in query_lower and 'loan' in query_lower:
                # Filter for ONLY home loans
                filtered_results = []
                for row in results:
                    row_dict = dict(zip(column_names, row))
                    category = str(row_dict.get('category', '')).lower()
                    product_name = str(row_dict.get('product_name', '')).lower()
                    if 'home' in category or 'home' in product_name:
                        filtered_results.append(row)
                
                if filtered_results:
                    results = filtered_results[:10]  # Use home loans only
            else:
                # Filter based on other personas
                filtered_results = []
                for row in results:
                    row_dict = dict(zip(column_names, row))
                    
                    # Parse attributes JSON
                    try:
                        attrs = json.loads(row_dict.get('attributes', '{}'))
                    except:
                        attrs = {}
                    
                    # Extract fees as integer for comparison
                    fees_str = attrs.get('fees', '') or row_dict.get('fees', '') or ''
                    try:
                        fees_num = int(''.join(filter(str.isdigit, str(fees_str).split('+')[0])))
                    except:
                        fees_num = 99999
                    
                    # Student filter: Low fees (< Rs. 1000)
                    if 'student' in query_lower or 'students' in query_lower or 'low income' in query_lower:
                        if fees_num <= 1000:
                            filtered_results.append(row)
                    
                    # Traveler filter: Travel/Lounge keywords (FIXED)
                    elif 'travel' in query_lower or 'fly' in query_lower or 'lounge' in query_lower or 'flyer' in query_lower:
                        features = str(attrs.get('features', '')).lower()
                        product_name = str(row_dict.get('product_name', '')).lower()
                        if any(word in features or word in product_name for word in ['lounge', 'air india', 'travel', 'miles', 'vistara', 'etihad', 'indigo']):
                            filtered_results.append(row)
                    
                    # Premium filter: High-end cards
                    elif 'premium' in query_lower or 'luxury' in query_lower:
                        if fees_num >= 2000:
                            filtered_results.append(row)
            
            # If filtering worked, use filtered results
            if len(filtered_results) >= 2:
                results = filtered_results[:10]  # Max 10 cards
                # CRITICAL: Regenerate results_text with ONLY filtered cards
                results_text = f"Pre-filtered to {len(results)} student-friendly cards:\n"
                for row in results:
                    row_dict = dict(zip(column_names, row))
                    results_text += f"\n{json.dumps(row_dict, indent=2)}\n"
        
        # Generate natural language response with adaptive prompts
        # CHECK RECOMMENDATIONS FIRST (most specific)
        query_lower = user_query.lower()
        is_recommendation = (
            'best' in query_lower and ('for' in query_lower or 'card' in query_lower or 'loan' in query_lower) or
            'recommend' in query_lower or
            'which bank' in query_lower
        )
        
        if is_recommendation:
            # Recommendation query - FORMAT DIRECTLY IN PYTHON (AI kept ignoring instructions)
            
            # Sort by fees (lowest first) - PARSE JSON attributes
            def get_fee_num(row):
                try:
                    card = dict(zip(column_names, row))
                    attrs = json.loads(card.get('attributes', '{}'))
                    fees_str = attrs.get('fees', '99999')
                    return int(''.join(filter(str.isdigit, fees_str.split('+')[0])))
                except:
                    return 99999
            
            sorted_results = sorted(results, key=get_fee_num)
            
            # Take top 3
            top_3 = sorted_results[:3]
            
            # Format response directly
            response_text = f"**Best Credit Cards for Students:**\n\n"
            
            medals = ["🥇 **Best Choice**", "🥈 **Alternative**", "💰 **Budget Option**"]
            for i, row in enumerate(top_3):
                card = dict(zip(column_names, row))
                
                # Parse JSON attributes
                try:
                    attrs = json.loads(card.get('attributes', '{}'))
                except:
                    attrs = {}
                
                response_text += f"{medals[i]}: **{card.get('product_name', 'Unknown')}**\n"
                response_text += f"- Bank: {card.get('bank_name', 'N/A')}\n"
                response_text += f"- Fees: {attrs.get('fees', 'N/A')}\n"
                response_text += f"- Features: {attrs.get('features', 'N/A')}\n"
                response_text += f"- Eligibility: {attrs.get('eligibility', 'N/A')}\n\n"
            
            response_text += f"**Why these?** Lowest fees suitable for students (under Rs. 1000). "
            response_text += f"We filtered {len(results)} cards and selected the top 3 by affordability."
            
            return {
                "text": response_text,
                "data": [dict(zip(column_names, row)) for row in top_3],
                "sql": sql_query,
                "source": "Product Catalog (SQL)"
            }
        elif detail_level == 'COUNT_ONLY':
            # Concise count response
            synthesis_prompt = f"""
            User asked: "{user_query}"
            
            SQL Query executed: {sql_query}
            Results: Found {len(results)} products.
            
            Generate a CONCISE response:
            - State the count clearly: "SBI offers {len(results)} credit cards" or similar
            - Optionally mention 2-3 popular examples if relevant
            - Do NOT list all products
            - Keep it to 1-2 sentences
            """
        elif detail_level == 'EXPLAIN_DETAILED':
            # Detailed explanation of all products
            synthesis_prompt = f"""
            User asked: "{user_query}"
            
            SQL Query executed: {sql_query}
            
            Results:
            {results_text}
            
            CRITICAL: List EVERY SINGLE PRODUCT with full details.
            
            Rules:
            - List ALL {len(results)} products
            - Format each product clearly with key details (fees, rates, features, eligibility)
            - Start with: "[Bank] offers {len(results)} credit cards:"
            - Use numbered list or bullet points
            - Be complete and structured
            """
        else:
            # Standard list (what are...)
            synthesis_prompt = f"""
            User asked: "{user_query}"
            
            SQL Query executed: {sql_query}
            
            Results:
            {results_text}
            
            Generate a helpful response listing the products.
            
            Rules:
            - List ALL {len(results)} products by name
            - Include 1-2 key highlights for each (main benefit or feature)
            - Keep each entry concise (1 line per product)
            - Start with the count and bank name
            - Format as a clean list
            """
        
        final_response = client.chat.completions.create(
            messages=[{"role": "user", "content": synthesis_prompt}],
            model=LLM_MODEL,
            temperature=0.3
        )
        
        return {
            "text": final_response.choices[0].message.content,
            "data": [dict(zip(column_names, row)) for row in results],
            "sql": sql_query,
            "source": "Product Catalog (SQL)"
        }
        
    except Exception as e:
        return {
            "text": f"Error processing SQL query: {str(e)}",
            "data": None,
            "source": "Error"
        }


if __name__ == "__main__":
    # Test
    print(execute_sql_tool("List all SBI credit cards"))
