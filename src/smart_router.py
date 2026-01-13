"""
Hybrid Smart Router for Banking Agent - PRODUCTION VERSION

4-step hybrid routing with production-safe fixes:
1. DB-Based Entity Detection (0ms) - Extract bank/category
2. Accuracy-Critical Intent Detection (0ms) - COUNT/LIST/EXPLAIN_ALL (NEVER overridden)
3. FAQ Similarity Check (~50ms) - Only if NOT accuracy-critical
4. LLM Fallback (~300ms) - Only for ambiguous 10-20%

Key Production Fixes:
- Accuracy-critical intents (COUNT/LIST/EXPLAIN_ALL) bypass FAQ and LLM
- CLARIFY intent when bank/category missing for structured queries
- Stricter COMPARE detection (requires "vs", "compare", or two products)
- Separate EXPLAIN vs EXPLAIN_ALL intents
- Dynamic bank detection from database
- Robust JSON parsing for LLM responses
"""

import re
import json
import logging
from typing import Dict, Optional, List, Tuple
from openai import OpenAI

from src.config import OPENAI_API_KEY, LLM_MODEL, PRODUCT_CATEGORIES
from src.vector_db import FAQVectorDB

# =============================================================================
# CONFIGURATION
# =============================================================================

# FAQ similarity threshold
FAQ_SIMILARITY_THRESHOLD = 0.50  # Slightly higher for safety

# Dynamic bank list (fetched from DB)
_supported_banks_cache = None

def get_supported_banks() -> List[str]:
    """Get banks from database (with caching)."""
    global _supported_banks_cache
    if _supported_banks_cache is None:
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            result = db.execute_raw_query(
                "SELECT DISTINCT bank_name FROM products WHERE bank_name IS NOT NULL"
            )
            _supported_banks_cache = [row['bank_name'] for row in result]
            if not _supported_banks_cache:
                _supported_banks_cache = ['SBI', 'HDFC']  # Fallback
        except:
            _supported_banks_cache = ['SBI', 'HDFC']
    return _supported_banks_cache

# Lazy initialization
_vector_db = None
_llm_client = None

def _get_vector_db():
    global _vector_db
    if _vector_db is None:
        _vector_db = FAQVectorDB()
    return _vector_db

def _get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(api_key=OPENAI_API_KEY)
    return _llm_client


# =============================================================================
# KEYWORD DEFINITIONS (FIXED)
# =============================================================================

# COUNT keywords - specific to counting
COUNT_KEYWORDS = [
    'how many', 'count', 'number of', 'total', 'kitne', 'kitna'
]

# LIST keywords - for listing (NO "kitne" - that's COUNT)
LIST_KEYWORDS = [
    'all', 'list', 'show', 'display', 'sab', 'sabhi', 'saare',
    'kya kya', 'konse', 'what are', 'which', 'names of'
]

# COMPARE - STRICT patterns only (removed "better", "ya")
COMPARE_PATTERNS = [
    r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bdifference between\b',
    r'\bcompared to\b', r'\bcomparison\b'
]

# RECOMMEND keywords
RECOMMEND_KEYWORDS = [
    'best', 'recommend', 'suggest', 'suitable', 'good for', 
    'better for', 'accha', 'sahi', 'which should i'
]

# EXPLAIN patterns (removed "what is" - too broad)
EXPLAIN_PATTERNS = [
    r'\bexplain\b', r'\bdetails of\b', r'\bfeatures of\b',
    r'\btell me about\b', r'\bdescribe\b', r'\binformation on\b'
]

# EXPLAIN_ALL patterns (separate intent for guaranteed completeness)
EXPLAIN_ALL_PATTERNS = [
    r'\bexplain all\b', r'\bdetails of all\b', r'\ball.*explain\b',
    r'\bexplain.*all\b', r'\btell me about all\b'
]

# Greetings
GREETINGS = [
    'hi', 'hello', 'hey', 'namaste', 'good morning', 'good afternoon',
    'good evening', 'hola', 'kaise ho', 'kya hal'
]


# =============================================================================
# STEP 1: ENTITY EXTRACTION (DB-Based)
# =============================================================================

def extract_entities(query: str) -> Dict:
    """
    Extract entities from query using database values.
    
    Returns entity signals for routing decisions.
    """
    query_lower = query.lower().strip()
    banks = get_supported_banks()
    
    # Extract bank from query
    bank = None
    for b in banks:
        if b.lower() in query_lower:
            bank = b
            break
    
    # Extract category (specific before generic)
    category = None
    category_patterns = [
        (r'\bhome loan', 'Home Loan'),
        (r'\bcredit card', 'Credit Card'),
        (r'\bdebit card', 'Debit Card'),
        (r'\b(car loan|personal loan|education loan|gold loan|two wheeler)', 'Loan'),
        (r'\bloan\b', 'Loan'),
        (r'\b(scheme|plan|saving|fd|fixed deposit)', 'Scheme'),
    ]
    
    for pattern, cat in category_patterns:
        if re.search(pattern, query_lower):
            category = cat
            break
    
    # Fallback to config categories
    if not category:
        for cat in PRODUCT_CATEGORIES:
            if cat.lower() in query_lower:
                category = cat
                break
    
    # Detect intent signals
    has_count = any(kw in query_lower for kw in COUNT_KEYWORDS)
    has_list = any(kw in query_lower for kw in LIST_KEYWORDS) and not has_count
    has_compare = any(re.search(p, query_lower) for p in COMPARE_PATTERNS)
    has_recommend = any(kw in query_lower for kw in RECOMMEND_KEYWORDS)
    has_explain_all = any(re.search(p, query_lower) for p in EXPLAIN_ALL_PATTERNS)
    has_explain = any(re.search(p, query_lower) for p in EXPLAIN_PATTERNS) and not has_explain_all
    
    # Check for greeting
    is_greeting = query_lower.strip() in GREETINGS or any(
        query_lower == g or query_lower.startswith(g + ' ') for g in GREETINGS
    )
    
    return {
        'bank': bank,
        'category': category,
        'has_count_signal': has_count,
        'has_list_signal': has_list,
        'has_compare_signal': has_compare,
        'has_recommend_signal': has_recommend,
        'has_explain_signal': has_explain,
        'has_explain_all_signal': has_explain_all,
        'is_greeting': is_greeting,
        'is_accuracy_critical': has_count or has_list or has_explain_all
    }


# =============================================================================
# STEP 2: ACCURACY-CRITICAL ROUTING (NEVER OVERRIDDEN)
# =============================================================================

def route_accuracy_critical(entities: Dict, query: str) -> Optional[Dict]:
    """
    Route accuracy-critical intents with guaranteed determinism.
    
    These intents are NEVER overridden by FAQ or LLM:
    - COUNT: Exact number of products
    - LIST: Complete product list
    - EXPLAIN_ALL: All products with details
    
    Also handles vague single-word queries with CLARIFY.
    
    Returns routing result or None if not accuracy-critical.
    """
    bank = entities['bank']
    category = entities['category']
    query_lower = query.lower().strip()
    
    # GREETING - Always handle first
    if entities['is_greeting']:
        return {'intent': 'GREETING', 'confidence': 0.99, 'path': 'GREETING'}
    
    # === VAGUE QUERY DETECTION ===
    # Single-word or very short banking terms should ask for clarification
    vague_terms = [
        'loan', 'loans', 'credit', 'debit', 'card', 'cards',
        'credit card', 'debit card', 'home loan', 'car loan',
        'account', 'accounts', 'bank', 'banking', 'scheme', 'schemes'
    ]
    
    is_vague = query_lower in vague_terms or (
        len(query_lower.split()) <= 2 and 
        any(term in query_lower for term in vague_terms) and
        not bank and  # No specific bank mentioned
        not entities['has_count_signal'] and
        not entities['has_list_signal'] and
        not entities['has_explain_signal'] and
        not entities['has_recommend_signal']
    )
    
    if is_vague:
        # Create specific clarification message based on category
        if category:
            clarify_msg = f"I can help you with {category}s! What would you like to know?\n\n" \
                         f"• **List** all {category}s from a specific bank\n" \
                         f"• **Compare** different {category}s\n" \
                         f"• **Recommend** the best {category} for you\n" \
                         f"• **Apply** - how to apply for a {category}"
        else:
            clarify_msg = "What would you like to know? Please specify:\n\n" \
                         "• Which **bank** (SBI, HDFC, etc.)?\n" \
                         "• What **product type** (Credit Card, Loan, etc.)?\n" \
                         "• What **action** (list all, count, compare, recommend)?"
        
        return {'intent': 'CLARIFY', 'confidence': 0.95, 'path': 'VAGUE_QUERY',
                'clarify_message': clarify_msg}
    
    # COUNT - Requires bank OR category context
    if entities['has_count_signal']:
        if bank or category:
            return {'intent': 'COUNT', 'confidence': 0.95, 'path': 'ACCURACY_CRITICAL'}
        else:
            return {'intent': 'CLARIFY', 'confidence': 0.90, 'path': 'NEEDS_CONTEXT',
                    'clarify_message': 'Which bank or product type would you like me to count?'}
    
    # EXPLAIN_ALL - Requires bank OR category
    if entities['has_explain_all_signal']:
        if bank or category:
            return {'intent': 'EXPLAIN_ALL', 'confidence': 0.95, 'path': 'ACCURACY_CRITICAL'}
        else:
            return {'intent': 'CLARIFY', 'confidence': 0.90, 'path': 'NEEDS_CONTEXT',
                    'clarify_message': 'Which bank or product type would you like me to explain?'}
    
    # LIST - Requires bank OR category
    if entities['has_list_signal']:
        if bank or category:
            return {'intent': 'LIST', 'confidence': 0.90, 'path': 'ACCURACY_CRITICAL'}
        else:
            return {'intent': 'CLARIFY', 'confidence': 0.85, 'path': 'NEEDS_CONTEXT',
                    'clarify_message': 'Which bank or product type would you like me to list?'}
    
    # COMPARE - Strict detection
    if entities['has_compare_signal']:
        return {'intent': 'COMPARE', 'confidence': 0.90, 'path': 'DB_SIGNALS'}
    
    # RECOMMEND
    if entities['has_recommend_signal']:
        return {'intent': 'RECOMMEND', 'confidence': 0.90, 'path': 'DB_SIGNALS'}
    
    # EXPLAIN (single product/category)
    if entities['has_explain_signal']:
        if bank or category:
            return {'intent': 'EXPLAIN', 'confidence': 0.85, 'path': 'DB_SIGNALS'}
    
    # Implicit LIST: bank + category without other signals
    if bank and category:
        return {'intent': 'LIST', 'confidence': 0.70, 'path': 'IMPLICIT_LIST'}
    
    return None  # Not determinable from DB signals


# =============================================================================
# STEP 3: FAQ SIMILARITY CHECK (Only for non-accuracy-critical)
# =============================================================================

def check_faq_similarity(query: str, bank: Optional[str] = None) -> Optional[Dict]:
    """
    Check FAQ similarity - ONLY for procedural queries.
    
    Skipped entirely if query is accuracy-critical (COUNT/LIST/EXPLAIN_ALL).
    """
    try:
        vector_db = _get_vector_db()
        results = vector_db.query_faqs(
            query,
            bank_filter=bank,
            n_results=1,
            include_distances=True
        )
        
        if results and len(results) > 0:
            top_match = results[0]
            similarity = top_match.get('similarity', 0)
            
            logging.debug(f"[FAQ] Match: {similarity:.3f}")
            
            if similarity >= FAQ_SIMILARITY_THRESHOLD:
                return top_match
        
        return None
        
    except Exception as e:
        logging.warning(f"[FAQ Check] Error: {e}")
        return None


# =============================================================================
# STEP 4: LLM FALLBACK (Robust JSON Parsing)
# =============================================================================

def llm_classify(query: str, entities: Dict, chat_history: Optional[List] = None) -> Dict:
    """
    LLM classification for ambiguous queries with robust JSON parsing.
    """
    client = _get_llm_client()
    
    # Build history context
    history_context = ""
    if chat_history and len(chat_history) > 0:
        recent = chat_history[-3:]
        history_context = "\n".join([
            f"- {msg.get('role', 'user')}: {msg.get('content', '')[:80]}"
            for msg in recent
        ])
    
    prompt = f"""Classify this banking query into ONE intent.

Query: "{query}"
Bank detected: {entities.get('bank', 'None')}
Category detected: {entities.get('category', 'None')}
Recent chat: {history_context if history_context else 'None'}

Intents (choose ONE):
- FAQ: Asking about process, procedure, documents, how-to, eligibility
- RECOMMEND: Wants product suggestions/recommendations
- FOLLOWUP: Referring to previous conversation (it, them, more, that)
- GREETING: Just saying hello
- UNKNOWN: Cannot determine

Return ONLY valid JSON: {{"intent": "...", "confidence": 0.0-1.0}}"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # ROBUST JSON PARSING
        # Remove markdown code blocks
        result_text = re.sub(r'^```json?\s*', '', result_text)
        result_text = re.sub(r'\s*```$', '', result_text)
        result_text = result_text.strip()
        
        # Find JSON object boundaries
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = result_text[start_idx:end_idx]
            result = json.loads(json_str)
            return {
                'intent': result.get('intent', 'UNKNOWN'),
                'confidence': float(result.get('confidence', 0.5))
            }
        
        return {'intent': 'UNKNOWN', 'confidence': 0.3}
        
    except Exception as e:
        logging.warning(f"[LLM Classify] Error: {e}")
        return {'intent': 'UNKNOWN', 'confidence': 0.3}


# =============================================================================
# MAIN ROUTER
# =============================================================================

def smart_route(query: str, chat_history: Optional[List] = None) -> Dict:
    """
    Production-safe hybrid router.
    
    Routing priority:
    1. GREETING (instant)
    2. ACCURACY-CRITICAL: COUNT, LIST, EXPLAIN_ALL (never overridden)
    3. DB SIGNALS: COMPARE, RECOMMEND, EXPLAIN
    4. FAQ SIMILARITY (only if not accuracy-critical)
    5. LLM FALLBACK
    
    Returns:
        {
            'intent': str,
            'confidence': float,
            'bank': str or None,
            'category': str or None,
            'routing_path': str,
            'faq_match': dict or None,
            'original_query': str,
            'clarify_message': str or None  # For CLARIFY intent
        }
    """
    logging.info(f"[SmartRouter] Processing: {query}")
    
    # === STEP 1: Entity Extraction ===
    entities = extract_entities(query)
    logging.debug(f"[Step 1] Entities: {entities}")
    
    # === STEP 2: Accuracy-Critical Routing (HIGHEST PRIORITY) ===
    critical_result = route_accuracy_critical(entities, query)
    if critical_result:
        intent = critical_result['intent']
        logging.info(f"[Step 2] Accuracy-critical: {intent} ({critical_result['confidence']:.2f})")
        return {
            'intent': intent,
            'confidence': critical_result['confidence'],
            'bank': entities['bank'],
            'category': entities['category'],
            'routing_path': critical_result['path'],
            'faq_match': None,
            'original_query': query,
            'clarify_message': critical_result.get('clarify_message')
        }
    
    # === STEP 3: FAQ Similarity (Only for non-accuracy-critical) ===
    # Skip if we detected strong DB signals
    if not entities['is_accuracy_critical']:
        faq_match = check_faq_similarity(query, entities.get('bank'))
        if faq_match:
            logging.info(f"[Step 3] FAQ Match: {faq_match.get('similarity', 0):.3f}")
            return {
                'intent': 'FAQ',
                'confidence': 0.90,
                'bank': entities['bank'],
                'category': entities['category'],
                'routing_path': 'FAQ_SIMILARITY',
                'faq_match': faq_match,
                'original_query': query,
                'clarify_message': None
            }
    
    # === STEP 4: LLM Fallback ===
    logging.info("[Step 4] Using LLM fallback...")
    llm_result = llm_classify(query, entities, chat_history)
    
    return {
        'intent': llm_result['intent'],
        'confidence': llm_result['confidence'],
        'bank': entities['bank'],
        'category': entities['category'],
        'routing_path': 'LLM_FALLBACK',
        'faq_match': None,
        'original_query': query,
        'clarify_message': None
    }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    test_queries = [
        # Accuracy-critical (never FAQ/LLM)
        ("SBI credit cards list", "LIST"),
        ("how many HDFC loans", "COUNT"),
        ("explain all SBI debit cards", "EXPLAIN_ALL"),
        
        # Missing context → CLARIFY
        ("how many cards", "CLARIFY"),
        ("list all loans", "CLARIFY"),
        
        # FAQ (procedural)
        ("how to apply for loan", "FAQ"),
        ("what documents needed", "FAQ"),
        
        # Recommendations
        ("best credit card for students", "RECOMMEND"),
        
        # Compare (strict)
        ("SBI vs HDFC credit cards", "COMPARE"),
        
        # Greeting
        ("hello", "GREETING"),
        
        # Hinglish
        ("SBI debit cards kitne hai", "COUNT"),
        ("HDFC ke sab loans batao", "LIST"),
    ]
    
    print("\n" + "="*70)
    print("HYBRID ROUTER TEST (PRODUCTION VERSION)")
    print("="*70)
    
    for query, expected in test_queries:
        result = smart_route(query)
        status = "✅" if result['intent'] == expected else "❌"
        print(f"\n{status} Query: {query}")
        print(f"   Expected: {expected}, Got: {result['intent']}")
        print(f"   Confidence: {result['confidence']:.2f}, Path: {result['routing_path']}")
        if result.get('clarify_message'):
            print(f"   Clarify: {result['clarify_message']}")
