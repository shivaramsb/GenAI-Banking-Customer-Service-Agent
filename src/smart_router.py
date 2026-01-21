"""
Hybrid Smart Router for Banking Agent 

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

from src.config import OPENAI_API_KEY, LLM_MODEL
from src.vector_db import FAQVectorDB

# =============================================================================
# CONFIGURATION
# =============================================================================

# FAQ similarity threshold (lowered for better recall)
FAQ_SIMILARITY_THRESHOLD = 0.40  # Lower threshold catches more FAQ matches

# Dynamic bank list (fetched from DB)
_supported_banks_cache = None
_banks_cache_time = None

def get_supported_banks(refresh: bool = False) -> List[str]:
    """Get banks from database (with caching and refresh support)."""
    global _supported_banks_cache, _banks_cache_time
    import time
    
    # Refresh cache if requested or older than 5 minutes
    cache_stale = _banks_cache_time and (time.time() - _banks_cache_time > 300)
    
    if _supported_banks_cache is None or refresh or cache_stale:
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            result = db.execute_raw_query(
                "SELECT DISTINCT bank_name FROM products WHERE bank_name IS NOT NULL"
            )
            _supported_banks_cache = [row['bank_name'] for row in result]
            _banks_cache_time = time.time()
            if not _supported_banks_cache:
                _supported_banks_cache = ['SBI', 'HDFC']  # Fallback
        except:
            _supported_banks_cache = ['SBI', 'HDFC']
    return _supported_banks_cache


# Dynamic category list (fetched from DB)
_supported_categories_cache = None
_categories_cache_time = None

def get_supported_categories(refresh: bool = False) -> List[str]:
    """Get categories from database (with caching and refresh support)."""
    global _supported_categories_cache, _categories_cache_time
    import time
    
    # Refresh cache if requested or older than 5 minutes
    cache_stale = _categories_cache_time and (time.time() - _categories_cache_time > 300)
    
    if _supported_categories_cache is None or refresh or cache_stale:
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            result = db.execute_raw_query(
                "SELECT DISTINCT category FROM products WHERE category IS NOT NULL"
            )
            _supported_categories_cache = [row['category'] for row in result]
            _categories_cache_time = time.time()
            if not _supported_categories_cache:
                _supported_categories_cache = ['Credit Card', 'Debit Card', 'Loan', 'Scheme']  # Fallback
        except:
            _supported_categories_cache = ['Credit Card', 'Debit Card', 'Loan', 'Scheme']
    return _supported_categories_cache


def build_category_patterns(categories: List[str]) -> List[Tuple[str, str]]:
    """
    Build regex patterns dynamically from category list.
    
    Generates both exact matches and partial term patterns.
    Example: 'Credit Card' generates:
        - r'\bcredit card' → 'Credit Card' (exact)
        - r'\bcredit\b' → 'Credit Card' (partial)
    """
    patterns = []
    
    for cat in categories:
        cat_lower = cat.lower()
        
        # Exact match pattern (e.g., "credit card")
        patterns.append((rf'\b{cat_lower}', cat))
        
        # Partial term patterns (e.g., "credit" → "Credit Card")
        words = cat_lower.split()
        if len(words) > 1:
            # Add first word as partial match (e.g., "credit" for "Credit Card")
            patterns.append((rf'\b{words[0]}\b', cat))
        
        # Special case for plurals (e.g., "loans" → "Loan")
        if not cat_lower.endswith('s'):
            patterns.append((rf'\b{cat_lower}s\b', cat))
    
    return patterns

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
    'how many', 'count', 'number of', 'total'
]

# LIST keywords - for listing
LIST_KEYWORDS = [
    'all', 'list', 'show', 'display', 'what are', 'which', 'names of'
]

# COMPARE - STRICT patterns only (removed "better", "ya")
COMPARE_PATTERNS = [
    r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bdifference between\b',
    r'\bcompared to\b', r'\bcomparison\b'
]

# RECOMMEND keywords
RECOMMEND_KEYWORDS = [
    'best', 'recommend', 'suggest', 'suitable', 'good for', 
    'better for', 'which should i'
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
    'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'
]




# =============================================================================
# STEP 1: ENTITY EXTRACTION (DB-Based)
# =============================================================================

def extract_entities(query: str) -> Dict:
    """
    Extract entities from query using database values.
    
    Returns entity signals for routing decisions.
    Now extracts ALL banks for COMPARE queries.
    """
    query_lower = query.lower().strip()
    banks = get_supported_banks()
    
    # Extract ALL banks from query (for COMPARE queries)
    banks_found = []
    for b in banks:
        if b.lower() in query_lower:
            banks_found.append(b)
    
    # Primary bank (first found) for backward compatibility
    bank = banks_found[0] if banks_found else None
    
    # Extract category - DYNAMIC from DB
    category = None
    categories = get_supported_categories()
    category_patterns = build_category_patterns(categories)
    
    for pattern, cat in category_patterns:
        if re.search(pattern, query_lower):
            category = cat
            break
    
    # Detect intent signals (order matters for priority)
    has_count = any(kw in query_lower for kw in COUNT_KEYWORDS)
    has_compare = any(re.search(p, query_lower) for p in COMPARE_PATTERNS)
    has_recommend = any(kw in query_lower for kw in RECOMMEND_KEYWORDS)
    has_explain_all = any(re.search(p, query_lower) for p in EXPLAIN_ALL_PATTERNS)
    has_explain = any(re.search(p, query_lower) for p in EXPLAIN_PATTERNS) and not has_explain_all
    
    # LIST is only detected if no higher-priority intent is present
    has_list = (
        any(kw in query_lower for kw in LIST_KEYWORDS) and 
        not has_count and 
        not has_compare and  # "compare all" should be COMPARE, not LIST
        not has_recommend    # "best all" should be RECOMMEND, not LIST
    )
    
    # Check for greeting
    is_greeting = query_lower.strip() in GREETINGS or any(
        query_lower == g or query_lower.startswith(g + ' ') for g in GREETINGS
    )
    
    # Detect FAQ-like patterns (to avoid false CLARIFY)
    faq_patterns = [
        r'\b(how to|how do i|how can i|process|procedure|apply|document|eligibility|requirement|help)\b',
        r'\b(what is|what are|kya hai|kaise)\b',
        r'\b(create|open|activate|close|cancel|block)\s+(account|card|loan)\b',  # Account procedures
    ]
    has_faq_pattern = any(re.search(p, query_lower) for p in faq_patterns)
    
    return {
        'bank': bank,
        'banks_found': banks_found,  # All banks for COMPARE
        'category': category,
        'has_count_signal': has_count,
        'has_list_signal': has_list,
        'has_compare_signal': has_compare,
        'has_recommend_signal': has_recommend,
        'has_explain_signal': has_explain,
        'has_explain_all_signal': has_explain_all,
        'has_faq_pattern': has_faq_pattern,
        'is_greeting': is_greeting,
        'is_accuracy_critical': has_count or has_list or has_explain_all
    }


# =============================================================================
# STEP 2: ACCURACY-CRITICAL ROUTING (NEVER OVERRIDDEN)
# =============================================================================

def route_accuracy_critical(entities: Dict, query: str) -> Optional[Dict]:
    """
    Route using EVIDENCE-BASED VALIDATION (Production-Grade).
    
    3-Step Process:
    1. Scope Resolver: Extract bank/category from DB
    2. Evidence Retrieval: Gather DB count + FAQ similarity
    3. Operation Validation: Decide based on evidence, not keywords
    
    Key: COUNT must be DB-validated, not keyword-detected.
    
    Returns routing result or None if not determinable.
    """
    from src.evidence_router import route_with_evidence
    
    bank = entities['bank']
    category = entities['category']
    query_lower = query.lower().strip()
    
    # GREETING - Always handle first
    if entities['is_greeting']:
        return {'intent': 'GREETING', 'confidence': 0.99, 'path': 'GREETING'}
    
    # === VAGUE QUERY DETECTION ===
    # Single-word or very short banking terms should ask for clarification
    # BUT: Exclude queries with FAQ patterns (how to, apply, eligibility, etc.)
    # AND: Exclude if we have bank context from history!
    vague_terms = [
        'loan', 'loans', 'credit', 'debit', 'card', 'cards',
        'credit card', 'debit card', 'home loan', 'car loan',
        'account', 'accounts', 'bank', 'banking', 'scheme', 'schemes'
    ]
    
    # Only consider vague if:
    # - No FAQ pattern detected
    # - No bank context (from current query OR history)
    # - No strong intent signals
    is_vague = (
        not entities.get('has_faq_pattern', False) and  # Skip if FAQ-like
        not bank and  # Skip if we have bank context (including from history!)
        (query_lower in vague_terms or (
            len(query_lower.split()) <= 2 and 
            any(term in query_lower for term in vague_terms) and
            not entities['has_count_signal'] and
            not entities['has_list_signal'] and
            not entities['has_explain_signal'] and
            not entities['has_recommend_signal']
        ))
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
    
    # === EVIDENCE-BASED ROUTING ===
    # Use new evidence router for all structured queries
    evidence_result = route_with_evidence(query, entities)
    
    # If evidence router returned a result, use it
    if evidence_result:
        # Map operations back to intents for compatibility
        intent_map = {
            'COUNT': 'COUNT',
            'LIST': 'LIST',
            'EXPLAIN': 'EXPLAIN',
            'COMPARE': 'COMPARE',
            'RECOMMEND': 'RECOMMEND',
            'FAQ': 'FAQ',
            'CLARIFY': 'CLARIFY',
            'LLM_FALLBACK': 'UNKNOWN'
        }
        
        primary_intent = intent_map.get(evidence_result['intent'], 'UNKNOWN')
        
        # Return enhanced result with evidence metadata
        return {
            'intent': primary_intent,
            'confidence': evidence_result['confidence'],
            'path': evidence_result['path'],
            'operations': evidence_result.get('operations', [primary_intent]),  # Keep operations list
            'evidence': evidence_result.get('evidence'),
            'scope': evidence_result.get('scope')
        }
    
    # COMPARE - Strict detection (fallback if evidence router didn't catch it)
    if entities['has_compare_signal']:
        return {'intent': 'COMPARE', 'confidence': 0.90, 'path': 'DB_SIGNALS'}
    
    # RECOMMEND (fallback)
    if entities['has_recommend_signal']:
        return {'intent': 'RECOMMEND', 'confidence': 0.90, 'path': 'DB_SIGNALS'}
    
    # EXPLAIN (single product/category) (fallback)
    if entities['has_explain_signal']:
        if bank or category:
            return {'intent': 'EXPLAIN', 'confidence': 0.85, 'path': 'DB_SIGNALS'}
    
    # Implicit LIST: bank + category without other signals (fallback)
    # BUT: Don't trigger for FAQ-like queries ("how to apply", "process", etc.)
    if bank and category and not entities.get('has_faq_pattern', False):
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
    
    # === STEP 0: Extract context from chat history (State Machine) ===
    from src.history_manager import HistoryStateManager
    from src.followup_router import FollowupRouter
    
    # 1. Reconstruct State
    history_manager = HistoryStateManager()
    state = history_manager.extract_state(chat_history)
    
    # 2. Check for Specific Follow-up Transitions
    followup_router = FollowupRouter()
    followup_result = followup_router.route_followup(query, state)
    
    if followup_result:
        logging.info(f"[SmartRouter] Followup Transition: {followup_result['routing_path']}")
        return followup_result  # Return immediately (Virtual Query Strategy)
    
    # === STEP 1: Entity Extraction from current query ===
    entities = extract_entities(query)
    
    # === MERGE: Fill missing entities from history state ===
    # If current query doesn't have bank/category, use persistent state
    if not entities['bank'] and state.bank:
        entities['bank'] = state.bank
        entities['banks_found'] = [state.bank]
        logging.info(f"[Context] Using bank from history: {entities['bank']}")
    
    if not entities['category'] and state.category:
        entities['category'] = state.category
        logging.info(f"[Context] Using category from history: {entities['category']}")
    
    logging.debug(f"[Step 1] Entities (merged): {entities}")
    
    # === STEP 2: Accuracy-Critical Routing (HIGHEST PRIORITY) ===
    critical_result = route_accuracy_critical(entities, query)
    if critical_result:
        intent = critical_result['intent']
        logging.info(f"[Step 2] Accuracy-critical: {intent} ({critical_result['confidence']:.2f})")
        return {
            'intent': intent,
            'confidence': critical_result['confidence'],
            'bank': entities['bank'],
            'banks_found': entities.get('banks_found', []),
            'category': entities['category'],
            'routing_path': critical_result['path'],
            'operations': critical_result.get('operations', [intent]),  # Include operations list
            'faq_match': None,
            'original_query': query,
            'clarify_message': critical_result.get('clarify_message'),
            'evidence': critical_result.get('evidence'),  # Include evidence for debugging
            'scope': critical_result.get('scope')  # Include scope for debugging
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
                'banks_found': entities.get('banks_found', []),
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
        'banks_found': entities.get('banks_found', []),
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
