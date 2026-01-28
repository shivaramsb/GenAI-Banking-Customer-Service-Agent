"""
Evidence-Based Router - Production-Grade Intent Classification

3-Step Validation:
1. Scope Resolver: Extract entities from DB (dynamic, not hardcoded)
2. Evidence Retrieval: Gather DB + FAQ evidence in parallel
3. Operation Validation: Decide operations based on evidence strength

Key Principle: COUNT must be DB-validated, not keyword-detected.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
import re

from src.query_validator import is_banking_query


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ScopeResult:
    """Scope extracted from query using DB reality."""
    bank: Optional[str]
    category: Optional[str]
    scope_strength: float  # 0.0-1.0
    
    @property
    def is_valid(self) -> bool:
        """Scope is valid if bank OR category exists."""
        return self.bank is not None or self.category is not None


@dataclass
class Evidence:
    """Evidence gathered from DB and FAQ sources."""
    db_count: int              # How many products in scope
    faq_top_score: float       # Best FAQ similarity (0-1)
    db_strength: float         # 1.0 if products exist, 0.0 otherwise
    faq_strength: float        # FAQ similarity score
    
    def __repr__(self):
        return f"Evidence(db_count={self.db_count}, faq_score={self.faq_top_score:.2f})"


@dataclass
class Operation:
    """An operation to execute."""
    name: str
    confidence: float
    
    def __repr__(self):
        return f"{self.name}({self.confidence:.2f})"


# =============================================================================
# STEP A: SCOPE RESOLVER (DB-Driven)
# =============================================================================

def resolve_scope(query: str, entities: Dict) -> ScopeResult:
    """
    Extract scope from query using DB entities (already extracted).
    
    Args:
        query: User query
        entities: Pre-extracted entities from smart_router
    
    Returns:
        ScopeResult with bank, category, and scope_strength
    """
    bank = entities.get('bank')
    category = entities.get('category')
    
    # Calculate scope strength
    if bank and category:
        scope_strength = 1.0
    elif bank or category:
        scope_strength = 0.7
    else:
        scope_strength = 0.0
    
    logging.debug(f"[Scope] Bank={bank}, Category={category}, Strength={scope_strength}")
    
    return ScopeResult(
        bank=bank,
        category=category,
        scope_strength=scope_strength
    )


# =============================================================================
# STEP B: EVIDENCE RETRIEVAL (Parallel, Fast)
# =============================================================================

def gather_evidence(query: str, scope: ScopeResult) -> Evidence:
    """
    Retrieve evidence from DB and FAQ in parallel.
    
    Total time: ~50ms (both run concurrently)
    
    Args:
        query: User query
        scope: Resolved scope
    
    Returns:
        Evidence object with DB and FAQ strength
    """
    from src.database import DatabaseManager
    from src.vector_db import FAQVectorDB
    
    db = DatabaseManager()
    vector_db = FAQVectorDB()
    
    # Parallel execution
    with ThreadPoolExecutor(max_workers=2) as executor:
        # DB evidence: How many products exist?
        def count_products():
            try:
                result = db.execute_raw_query(
                    """
                    SELECT COUNT(*) as count 
                    FROM products 
                    WHERE (? IS NULL OR bank_name = ?)
                      AND (? IS NULL OR category LIKE ?)
                    """,
                    (scope.bank, scope.bank, scope.category, f"%{scope.category}%" if scope.category else None)
                )
                return result[0]['count'] if result else 0
            except Exception as e:
                logging.warning(f"[Evidence] DB count failed: {e}")
                return 0
        
        # FAQ evidence: Is this a procedural question?
        def get_faq_similarity():
            try:
                results = vector_db.query_faqs(
                    user_query=query,  # Fix: use user_query parameter name
                    bank_filter=scope.bank,
                    n_results=1,
                    include_distances=True
                )
                if results and len(results) > 0:
                    return results[0].get('similarity', 0.0)
                return 0.0
            except Exception as e:
                logging.warning(f"[Evidence] FAQ similarity failed: {e}")
                return 0.0
        
        db_future = executor.submit(count_products)
        faq_future = executor.submit(get_faq_similarity)
        
        db_count = db_future.result()
        faq_score = faq_future.result()
    
    evidence = Evidence(
        db_count=db_count,
        faq_top_score=faq_score,
        db_strength=1.0 if db_count > 0 else 0.0,
        faq_strength=faq_score
    )
    
    logging.info(f"[Evidence] {evidence}")
    return evidence


# =============================================================================
# STEP C: OPERATION VALIDATION (Deterministic)
# =============================================================================

def validate_operations(query: str, scope: ScopeResult, evidence: Evidence) -> List[Operation]:
    """
    Determine which operations to execute based on evidence.
    
    Validation Rules:
    1. COUNT candidate: db_count > 0 AND faq_strength < 0.6 AND target is products
    2. FAQ candidate: faq_strength >= 0.6 OR (db_count == 0 AND faq_strength >= 0.4) OR target is non-product
    3. Multi-operation: Both candidates pass
    
    Args:
        query: User query
        scope: Resolved scope
        evidence: Gathered evidence
    
    Returns:
        List of operations to execute
    """
    operations = []
    query_lower = query.lower()
    
    # Detect operation signals in query (language hints, but not decisive)
    has_count_signal = any(kw in query_lower for kw in ['how many', 'count', 'total', 'number of'])
    has_list_signal = any(kw in query_lower for kw in ['list', 'show', 'all', 'display', 'what are'])
    has_compare_signal = any(pat in query_lower for pat in ['vs', 'versus', 'compare', 'difference between'])
    has_recommend_signal = any(kw in query_lower for kw in ['best', 'recommend', 'suggest', 'suitable'])
    has_explain_signal = any(kw in query_lower for kw in ['explain', 'details', 'tell me about', 'describe'])
    
    # === CRITICAL: Detect non-product targets ===
    # These indicate FAQ queries, not product queries
    non_product_targets = [
        'step', 'steps', 'process', 'procedure', 'way',
        'document', 'documents', 'requirement', 'requirements', 'paper', 'papers',
        'time', 'times', 'duration', 'period',
        'eligibility', 'eligible', 'qualify',
        'fee', 'fees', 'charge', 'charges', 'cost',
        'interest', 'rate', 'rates',
        'apply', 'application', 'applying',
        'approval', 'approve',
        'withdraw', 'withdrawal', 'limit'
    ]
    
    # Check if query target is non-product (FAQ indicator)
    target_is_non_product = any(target in query_lower for target in non_product_targets)
    
    if target_is_non_product:
        logging.debug(f"[Validation] 🎯 Non-product target detected (FAQ indicator)")
    
    # === RULE 1: COUNT CANDIDATE TEST ===
    # Products must exist and scope must be resolved
    # FAQ score is IRRELEVANT here - we check it later in decision logic
    is_count_candidate = (
        evidence.db_count > 0 and                    # Products exist
        scope.scope_strength >= 0.7 and              # Scope resolved
        not target_is_non_product                    # NOT asking about steps/docs/etc
    )
    
    # === RULE 2: FAQ CANDIDATE TEST ===
    is_faq_candidate = (
        evidence.faq_strength >= 0.6 or              # High FAQ similarity
        (evidence.db_count == 0 and                  # No products but
         evidence.faq_strength >= 0.4) or            # moderate FAQ match
        target_is_non_product                        # Query asks about non-product
    )
    
    logging.debug(f"[Validation] COUNT candidate: {is_count_candidate}, FAQ candidate: {is_faq_candidate}")
    
    # === DECISION LOGIC ===
    
    # Special case: Multi-operation detection
    # If query has BOTH count/list signals AND non-product targets like "apply"
    # Example: "how many SBI cards and how to apply"
    has_conjunction = any(conj in query_lower for conj in [' and ', ' & ', ', '])
    
    if (has_count_signal or has_list_signal) and target_is_non_product and has_conjunction and evidence.db_count > 0:
        # Execute BOTH operations
        if has_count_signal:
            operations.append(Operation('COUNT', confidence=0.90))
            logging.info(f"[Validation] ✅ COUNT operation (multi-op with FAQ)")
        elif has_list_signal:
            operations.append(Operation('LIST', confidence=0.85))
            logging.info(f"[Validation] ✅ LIST operation (multi-op with FAQ)")
        
        operations.append(Operation('FAQ', confidence=0.85))
        logging.info(f"[Validation] ✅ FAQ operation (multi-op with COUNT/LIST)")
        return operations
    
    # FAQ takes PRIORITY if target is non-product (single operation)
    if is_faq_candidate and target_is_non_product and not has_conjunction:
        operations.append(Operation('FAQ', confidence=0.95))
        logging.info(f"[Validation] ✅ FAQ operation (non-product target detected)")
        return operations  # Return immediately, don't add other operations
    
    # === PRIORITY ORDER: COUNT/LIST signals take priority over FAQ scores ===
    # Because COUNT/LIST queries with high FAQ similarity should still count products
    
    # COUNT operation (PRIORITY: check this BEFORE FAQ)
    if is_count_candidate and has_count_signal:
        operations.append(Operation('COUNT', confidence=0.95))
        logging.info(f"[Validation] ✅ COUNT operation (db_count={evidence.db_count})")
        return operations
    
    # LIST operation (PRIORITY: check this BEFORE FAQ)
    if is_count_candidate and has_list_signal and not has_count_signal:
        operations.append(Operation('LIST', confidence=0.90))
        logging.info(f"[Validation] ✅ LIST operation (db_count={evidence.db_count})")
        return operations

    # COMPARE operation (PRIORITY: check BEFORE FAQ)
    if has_compare_signal and evidence.db_count > 0:
        operations.append(Operation('COMPARE', confidence=0.90))
        logging.info(f"[Validation] ✅ COMPARE operation")
        return operations
    
    # RECOMMEND operation (PRIORITY: check BEFORE FAQ)
    if has_recommend_signal and evidence.db_count > 0:
        operations.append(Operation('RECOMMEND', confidence=0.90))
        logging.info(f"[Validation] ✅ RECOMMEND operation")
        return operations
    
    # EXPLAIN operation (PRIORITY: check BEFORE FAQ)
    if has_explain_signal and evidence.db_count > 0 and not has_list_signal:
        operations.append(Operation('EXPLAIN', confidence=0.85))
        logging.info(f"[Validation] ✅ EXPLAIN operation")
        return operations

    # PRIORITY 4: Implicit LIST (Smart Fork - Context-Aware)
    # Apply context to list products when bank + category are known
    # BUT: Skip if query is procedural (FAQ-like)
    if (scope.bank and scope.category and evidence.db_count > 0 and 
        not target_is_non_product and 
        not has_count_signal and 
        not has_compare_signal and
        not has_recommend_signal and
        not has_explain_signal):
        
        # CRITICAL: Detect procedural/FAQ patterns and skip implicit LIST
        # These queries should go to FAQ even with context
        procedural_patterns = [
            'how to', 'how do', 'how can', 'steps to', 'process to',
            'register', 'activate', 'apply for', 'get a', 'open a',
            'procedure', 'way to', 'method to', 'can i', 'do i need'
        ]
        
        query_lower = query.lower()
        is_procedural = any(pattern in query_lower for pattern in procedural_patterns)
        
        # Also check FAQ score - if HIGH, it's likely procedural
        is_high_faq = evidence.faq_strength >= 0.75
        
        if is_procedural or is_high_faq:
            logging.info(f"[Validation] ⚠️ Skipping implicit LIST - procedural query detected (faq_score={evidence.faq_strength:.2f})")
            # Let it fall through to FAQ check below
        else:
            # CRITICAL: Validate query is banking-related before applying context
            # This prevents random words (e.g., "shivaram") from triggering lists
            if is_banking_query(query):
                operations.append(Operation('LIST', confidence=0.85))
                logging.info(f"[Validation] ✅ LIST operation (Implicit Context Promotion: {scope.bank} {scope.category})")
                return operations
            else:
                # Query is NOT banking-related - refuse it
                operations.append(Operation('REFUSE', confidence=0.95))
                logging.warning(f"[Validation] ⚠️ REFUSE - Non-banking query with context: '{query}'")
                return operations
    
    # FAQ operation (only if no structured operation triggered)
    if is_faq_candidate and evidence.faq_strength >= 0.6:
        operations.append(Operation('FAQ', confidence=evidence.faq_strength))
        logging.info(f"[Validation] ✅ FAQ operation (faq_score={evidence.faq_strength:.2f})")
        return operations
    
    # Fallback: If no operations detected, use LLM
    if not operations:
        logging.warning(f"[Validation] ⚠️ No operations detected, using LLM fallback")
        operations.append(Operation('LLM_FALLBACK', confidence=0.5))
    
    return operations


# =============================================================================
# MAIN EVIDENCE-BASED ROUTER
# =============================================================================

def route_with_evidence(query: str, entities: Dict) -> Dict:
    """
    Evidence-based routing (replaces keyword matching).
    
    Returns routing result with operations, evidence, and confidence.
    
    Args:
        query: User query
        entities: Pre-extracted entities from smart_router
    
    Returns:
        Routing result dict
    """
    # Step A: Resolve scope
    scope = resolve_scope(query, entities)
    
    # If no scope, return CLARIFY immediately
    if not scope.is_valid:
        logging.info("[Evidence Router] ❌ No scope → CLARIFY")
        return {
            'intent': 'CLARIFY',
            'operations': ['CLARIFY'],
            'confidence': 0.95,
            'path': 'NO_SCOPE',
            'evidence': None
        }
    
    # Step B: Gather evidence
    evidence = gather_evidence(query, scope)
    
    # Step C: Validate operations
    operations = validate_operations(query, scope, evidence)
    
    # Return result (primary operation is first)
    primary_op = operations[0]
    
    logging.info(f"[Evidence Router] ✅ Operations: {[op.name for op in operations]}")
    
    return {
        'intent': primary_op.name,
        'operations': [op.name for op in operations],
        'confidence': primary_op.confidence,
        'path': 'EVIDENCE_BASED',
        'evidence': evidence,
        'scope': scope,
        # Pass through for handlers
        'bank': scope.bank,
        'category': scope.category,
        'product_name': entities.get('product_name')
    }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test cases
    test_cases = [
        ("how many SBI debit cards", {'bank': 'SBI', 'category': 'Debit Card'}),
        ("how many steps to apply for loan", {'bank': None, 'category': 'Loan'}),
        ("how many cards", {'bank': None, 'category': None}),
    ]
    
    print("\n" + "="*70)
    print("EVIDENCE-BASED ROUTER TEST")
    print("="*70)
    
    for query, entities in test_cases:
        print(f"\n📝 Query: {query}")
        print(f"   Entities: {entities}")
        result = route_with_evidence(query, entities)
        print(f"   ➜ Intent: {result['intent']}")
        print(f"   ➜ Operations: {result['operations']}")
        print(f"   ➜ Confidence: {result['confidence']:.2f}")
        print(f"   ➜ Evidence: {result.get('evidence')}")
