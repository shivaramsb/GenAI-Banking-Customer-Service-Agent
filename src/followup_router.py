
import logging
import re
from typing import Dict, Optional, Any
from src.history_manager import ContextState

class FollowupRouter:
    """
    Decides the Next Best Action based on User Query + Context State.
    Implements the Universal Follow-up Logic.
    """
    
    def route_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        """
        Check if query is a follow-up and return routing result if yes.
        Returns None if it's a new/unrelated query.
        """
        query_lower = query.lower().strip()
        
        # 1. Check for State Transitions based on Active Intent
        if state.active_intent == 'COUNT':
            return self._handle_count_followup(query_lower, state)
            
        elif state.active_intent == 'LIST':
            return self._handle_list_followup(query_lower, state)
            
        elif state.active_intent == 'RECOMMEND':
            return self._handle_recommend_followup(query_lower, state)
            
        elif state.active_intent == 'COMPARE':
            return self._handle_compare_followup(query_lower, state)
            
        # 2. Universal Follow-ups (Apply to any state if specific logic didn't catch it)
        # e.g. "Explain them" might apply generically
        
        return None

    def _handle_count_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        """COUNT -> LIST / EXPLAIN / COMPARE"""
        if not state.active_filters.get('bank') and not state.active_filters.get('category'):
            return None
        
        # Check for ordinal selection FIRST (e.g., "explain third", "details of 5th")
        # This should take priority over generic "explain" routing
        match = re.search(r'\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th)\b', query)
        if not match:
            # Fallback: try bare numbers (1-10) when used with "explain" context
            if 'explain' in query or 'details' in query or 'show' in query:
                match = re.search(r'\b([1-9]|10)\b', query)
        
        if match and state.last_response_meta.get('product_names'):
            index_map = {
                'first': 0, '1st': 0, '1': 0,
                'second': 1, '2nd': 1, '2': 1,
                'third': 2, '3rd': 2, '3': 2,
                'fourth': 3, '4th': 3, '4': 3,
                'fifth': 4, '5th': 4, '5': 4,
                'sixth': 5, '6th': 5, '6': 5,
                'seventh': 6, '7th': 6, '7': 6,
                'eighth': 7, '8th': 7, '8': 7,
                'ninth': 8, '9th': 8, '9': 8,
                'tenth': 9, '10th': 9, '10': 9
            }
            idx = index_map.get(match.group(1), 0)
            
            products = state.last_response_meta['product_names']
            if idx < len(products):
                target_product = products[idx].strip()
                return {
                    'intent': 'EXPLAIN',
                    'confidence': 0.98,
                    'routing_path': 'FOLLOWUP_ORDINAL_SELECTION',
                    'original_query': f"Explain {target_product}",
                    'product_name': target_product,
                    'bank': state.active_filters.get('bank'),
                    'category': state.active_filters.get('category')
                }
            
        # "List them", "Show me", "What are they"
        if re.search(r'\b(list|show|display|what are|names)\b', query):
            return {
                'intent': 'LIST',
                'confidence': 0.95,
                'bank': state.active_filters.get('bank'),
                'category': state.active_filters.get('category'),
                'routing_path': 'FOLLOWUP_COUNT_TO_LIST',
                'original_query': query
            }
            
        # "Explain them", "Details" (generic - explain ALL)
        if re.search(r'\b(explain|details|about)\b', query):
            return {
                'intent': 'EXPLAIN_ALL',
                'confidence': 0.95,
                'bank': state.active_filters.get('bank'),
                'category': state.active_filters.get('category'),
                'routing_path': 'FOLLOWUP_COUNT_TO_EXPLAIN',
                'original_query': query
            }
            
        return None

    def _handle_list_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        """LIST -> EXPLAIN / COMPARE / RECOMMEND"""
        
        # Debug logging
        logging.info(f"[FollowUp LIST] Query: '{query}'")
        logging.info(f"[FollowUp LIST] State intent: {state.active_intent}")
        logging.info(f"[FollowUp LIST] Products in state: {len(state.last_response_meta.get('product_names', []))}")
        
        # "Explain the first one", "Details of 1st", "explain 5th", "explain 5"
        # First try to match ordinal words/suffixes
        match = re.search(r'\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th)\b', query)
        if not match:
            # Fallback: try bare numbers (1-10) when used with "explain" context
            if 'explain' in query or 'details' in query or 'show' in query:
                match = re.search(r'\b([1-9]|10)\b', query)
        
        if match and state.last_response_meta.get('product_names'):
            index_map = {
                'first': 0, '1st': 0, '1': 0,
                'second': 1, '2nd': 1, '2': 1,
                'third': 2, '3rd': 2, '3': 2,
                'fourth': 3, '4th': 3, '4': 3,
                'fifth': 4, '5th': 4, '5': 4,
                'sixth': 5, '6th': 5, '6': 5,
                'seventh': 6, '7th': 6, '7': 6,
                'eighth': 7, '8th': 7, '8': 7,
                'ninth': 8, '9th': 8, '9': 8,
                'tenth': 9, '10th': 9, '10': 9
            }
            idx = index_map.get(match.group(1), 0)
            
            products = state.last_response_meta['product_names']
            if idx < len(products):
                target_product = products[idx].strip()
                logging.info(f"[FollowUp LIST] ✅ Routing to EXPLAIN: {target_product}")
                return {
                    'intent': 'EXPLAIN',
                    'confidence': 0.98,
                    'routing_path': 'FOLLOWUP_ORDINAL_SELECTION',
                    'original_query': f"Explain {target_product}", # Virtual Query
                    'product_name': target_product, # Explicit product for handler
                    'bank': state.active_filters.get('bank'),
                    'category': state.active_filters.get('category')
                }

        # "Which is best", "Recommend"
        if re.search(r'\b(best|recommend|suggest)\b', query):
            return {
                'intent': 'RECOMMEND',
                'confidence': 0.95,
                'bank': state.active_filters.get('bank'),
                'category': state.active_filters.get('category'),
                'routing_path': 'FOLLOWUP_LIST_TO_RECOMMEND',
                'original_query': query
            }

        return None

    def _handle_recommend_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        """RECOMMEND -> EXPLAIN (for 'why?', 'reason?')"""
        
        # "Why?", "Why that one?", "What are the benefits?", "Reasons?"
        if re.search(r'\b(why|reason|benefit|feature|advantage)\b', query):
            # Get the recommended product from state
            recommended = state.recommended_product
            
            if recommended:
                logging.info(f"[FollowUp RECOMMEND] Why? -> EXPLAIN: {recommended}")
                return {
                    'intent': 'EXPLAIN',
                    'confidence': 0.95,
                    'routing_path': 'FOLLOWUP_WHY_RECOMMENDATION',
                    'original_query': f"Explain {recommended}",
                    'product_name': recommended,
                    'bank': state.active_filters.get('bank'),
                    'category': state.active_filters.get('category')
                }
            else:
                logging.info(f"[FollowUp RECOMMEND] Why? but no recommended product in state")
        
        return None

    def _handle_compare_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        """COMPARE -> RECOMMEND (for 'which is better?')"""
        
        # "Which is better?", "Which should I choose?", "Which one?"
        if re.search(r'\b(which|better|best|choose|pick|select|prefer)\b', query):
            # Get compared products from state
            compared = state.compared_products
            
            if compared and len(compared) >= 2:
                logging.info(f"[FollowUp COMPARE] Which better? -> RECOMMEND from: {compared}")
                # Route to RECOMMEND with context about compared products
                products_text = " vs ".join(compared[:3])
                return {
                    'intent': 'RECOMMEND',
                    'confidence': 0.95,
                    'routing_path': 'FOLLOWUP_COMPARE_TO_RECOMMEND',
                    'original_query': f"Which is better: {products_text}",
                    'bank': state.active_filters.get('bank'),
                    'category': state.active_filters.get('category')
                }
            else:
                logging.info(f"[FollowUp COMPARE] Which better? but no compared products in state")
        
        return None
