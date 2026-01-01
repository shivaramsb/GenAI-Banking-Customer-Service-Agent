import logging
import json
from typing import List, Dict, Any

from src.database import DatabaseManager
from src.vector_db import FAQVectorDB

class MultiSourceRetriever:
    """
    Searches all available sources in parallel and fuses results.
    Eliminates need for semantic routing by always retrieving from all sources.
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.vector_db = FAQVectorDB()
        logging.info("MultiSourceRetriever initialized")
    
    def retrieve(self, query: str, max_results: int = 15, chat_history=None) -> Dict[str, Any]:
        """
        Main retrieval method - searches ALL sources in parallel.
        
        Args:
            query: User's search query
            max_results: Maximum number of fused results to return
            chat_history: Conversation history for context-aware filtering
            
        Returns:
            {
                'results': [...],  # Fused and ranked results
                'metadata': {
                    'sql_count': int,
                    'faq_count': int,
                    'sources_searched': [...],
                    'total_candidates': int,
                    'final_count': int
                }
            }
        """
        logging.info(f"Multi-source retrieval for query: {query}")
        
        # === PARALLEL RETRIEVAL ===
        sql_results = self._search_sql_products(query, n_results=50, chat_history=chat_history)
        faq_results = self._search_faq_vector(query, n_results=10)
        
        logging.info(f"Retrieved {len(sql_results)} SQL results, {len(faq_results)} FAQ results")
        
        # === FUSION ===
        all_results = self._combine_sources(sql_results, faq_results)
        
        # === DEDUPLICATION ===
        # Remove duplicates based on product_name to avoid showing same product twice
        unique_results = self._deduplicate_by_product_name(all_results)
        logging.info(f"After deduplication: {len(unique_results)} unique results")
        
        scored_results = self._score_and_rank(unique_results, query)
        final_results = self._ensure_diversity(scored_results[:max_results])
        
        # === METADATA ===
        metadata = {
            'sql_count': len(sql_results),
            'faq_count': len(faq_results),
            'sources_searched': ['SQL Product Catalog', 'FAQ Vector DB'],
            'total_candidates': len(all_results),
            'final_count': len(final_results)
        }
        
        return {'results': final_results, 'metadata': metadata}
    
    def _search_sql_products(self, query: str, n_results: int = 50, chat_history=None) -> List[Dict]:
        """
        Search SQL products database using intelligent SQL generation.
        
        Returns list of results in standard format.
        """
        from src.sql_tool import execute_sql_tool
        
        try:
            response = execute_sql_tool(query, chat_history=chat_history, skip_synthesis=True)
            sql_data = response.get('data', [])
            
            if not sql_data:
                return []
            
            # Format for fusion
            results = []
            for item in sql_data[:n_results]:
                results.append({
                    'content': self._format_product(item),
                    'source': 'SQL',
                    'confidence': 0.9,  # High confidence for structured data
                    'type': 'product',
                    'raw_data': item
                })
            
            return results
            
        except Exception as e:
            logging.warning(f"SQL search failed: {e}")
            return []
    
    def _search_faq_vector(self, query: str, n_results: int = 10) -> List[Dict]:
        """
        Search FAQ vector database using semantic similarity.
        
        Returns list of results in standard format.
        """
        try:
            faqs = self.vector_db.query_faqs(query, n_results=n_results)
            
            if not faqs:
                return []
            
            results = []
            for faq in faqs:
                results.append({
                    'content': f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}",
                    'source': 'FAQ',
                    'confidence': 0.85,  # Slightly lower for semantic search
                    'type': 'faq',
                    'raw_data': faq
                })
            
            return results
            
        except Exception as e:
            logging.warning(f"FAQ search failed: {e}")
            return []
    
    def _format_product(self, product_dict: Dict) -> str:
        """Format product data as readable text for synthesis."""
        name = product_dict.get('product_name', 'Unknown')
        bank = product_dict.get('bank_name', '')
        category = product_dict.get('category', '')
        
        # Parse attributes JSON if it's a string
        attrs = product_dict.get('attributes', {})
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except:
                attrs = {}
        
        # Build formatted text
        text = f"{bank} {name} ({category})\n"
        text += f"Fees: {attrs.get('fees', 'N/A')}\n"
        text += f"Features: {attrs.get('features', 'N/A')}\n"
        text += f"Eligibility: {attrs.get('eligibility', 'N/A')}"
        
        return text
    
    def _deduplicate_by_product_name(self, results: List[Dict]) -> List[Dict]:
        """
        Remove duplicate products based on product_name.
        Keeps the first occurrence of each unique product.
        """
        seen_products = set()
        unique_results = []
        
        for result in results:
            if result['type'] == 'product':
                product_name = result['raw_data'].get('product_name', '').strip()
                if product_name and product_name not in seen_products:
                    seen_products.add(product_name)
                    unique_results.append(result)
            else:
                # Keep all FAQ results
                unique_results.append(result)
        
        return unique_results
    
    def _combine_sources(self, *source_results: List[Dict]) -> List[Dict]:
        """Combine results from multiple sources into single list."""
        combined = []
        for source in source_results:
            combined.extend(source)
        return combined
    
    def _score_and_rank(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Re-rank results by relevance + confidence.
        
        Scoring factors:
        - Source confidence (SQL=0.9, FAQ=0.85)
        - Query-result similarity (keyword matching)
        - Result type preference based on query intent
        """
        query_lower = query.lower()
        
        for result in results:
            # Start with source confidence
            score = result['confidence']
            
            # Boost for query type alignment
            if any(word in query_lower for word in ['how to', 'procedure', 'apply', 'block', 'documents', 'activate']):
                # Procedural query - boost FAQs
                if result['type'] == 'faq':
                    score += 0.15
            elif any(word in query_lower for word in ['card', 'loan', 'product', 'fee', 'rate', 'interest', 'eligibility']):
                # Product query - boost SQL
                if result['type'] == 'product':
                    score += 0.15
            
            # Keyword overlap boost (simple but effective)
            query_words = set(query_lower.split())
            content_words = set(result['content'].lower().split())
            overlap = len(query_words & content_words) / max(len(query_words), 1)
            score += overlap * 0.2
            
            result['final_score'] = score
        
        # Sort by final score descending
        return sorted(results, key=lambda x: x['final_score'], reverse=True)
    
    def _ensure_diversity(self, results: List[Dict]) -> List[Dict]:
        """
        Ensure mix of sources in final results.
        
        Strategy: Return ranked results as-is (natural diversity from scoring).
        Future enhancement: Implement MMR or explicit source quotas.
        """
        # For now, simple implementation - ranking already provides natural diversity
        return results
