
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
            
        # "Explain them", "Details"
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
        """RECOMMEND -> EXPLAIN / COMPARE"""
        # "Why?", "Reason?"
        if re.search(r'\b(why|reason|feature|benefit)\b', query):
             # Assume recommending the LAST recommended product
            return {
                'intent': 'EXPLAIN',
                'confidence': 0.90,
                'routing_path': 'FOLLOWUP_EXPLAIN_RECOMMENDATION',
                'original_query': query,
                'product_name': state.last_response_meta.get('recommended_product'), # Explicit product
                 # We rely on the LLM or subsequent logic to know WHICH product derived from context if 'last_product_explained' isn't set
                 # Ideally HistoryManager extracts the recommended product name
            }
        return None

    def _handle_compare_followup(self, query: str, state: ContextState) -> Optional[Dict]:
        return None
