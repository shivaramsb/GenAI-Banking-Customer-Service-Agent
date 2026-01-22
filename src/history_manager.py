
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

# Caching for DB queries (Separate logic to avoid circular imports)
_supported_banks_cache = None
_supported_categories_cache = None

@dataclass
class ContextState:
    """Snapshot of the conversation state."""
    active_intent: Optional[str] = None          # Last intent (COUNT, LIST, etc.)
    active_filters: Dict[str, Any] = field(default_factory=dict) # current bank, category, etc.
    last_response_meta: Dict[str, Any] = field(default_factory=dict) # what bot showed last
    
    # Persistent entities (stickiest)
    bank: Optional[str] = None
    category: Optional[str] = None
    
    # Follow-up support
    recommended_product: Optional[str] = None     # Last recommended product
    compared_products: List[str] = field(default_factory=list)  # Last compared products
    
    def to_dict(self):
        return asdict(self)

class HistoryStateManager:
    """
    Reconstructs conversation state from chat history.
    """
    
    def __init__(self):
        self.banks = self._get_supported_banks()
        self.categories = self._get_supported_categories()
        
    def extract_state(self, chat_history: List[Dict]) -> ContextState:
        """
        Main entry point: Analyze history to build state.
        PRIORITY 1: Read from metadata (guaranteed accurate)
        FALLBACK: Parse text using regex (for backward compatibility)
       """
        if not chat_history:
            return ContextState()
            
        state = ContextState()
        
        # 1. Extract Persistent Entities (Bank/Category) from USER messages
        # Scan in reverse to find the latest
        user_msgs = [m for m in chat_history if m.get('role') == 'user']
        for msg in reversed(user_msgs):
            content = msg.get('content', '').lower()
            
            if not state.bank:
                state.bank = self._extract_bank(content)
            
            if not state.category:
                state.category = self._extract_category(content)
            
            if state.bank and state.category:
                break
                
        # 2. Extract Ephemeral State (Intent/Products) from BOT messages
        # SCAN ALL BOT MESSAGES (not just last) to find most recent LIST/COUNT
        bot_msgs = [m for m in chat_history if m.get('role') == 'assistant']
        
        # Search in reverse for the most recent LIST/COUNT (where products were shown)
        for bot_msg in reversed(bot_msgs):
            # PRIORITY 1: Check for metadata
            metadata = bot_msg.get('metadata', {})
            if metadata:
                intent = metadata.get('intent')
                
                # If this message has products, use it for state
                if intent in ['LIST', 'COUNT', 'EXPLAIN'] and metadata.get('product_names'):
                    state.active_intent = intent
                    state.last_response_meta['product_names'] = metadata.get('product_names', [])
                    state.last_response_meta['count_shown'] = metadata.get('count', 0)
                    
                    # Also get filters from metadata if available
                    if not state.bank and metadata.get('bank'):
                        state.bank = metadata.get('bank')
                    if not state.category and metadata.get('category'):
                        state.category = metadata.get('category')
                    
                    logging.info(f"[HistoryState] Using metadata: {intent}, {len(state.last_response_meta['product_names'])} products")
                    break  # Found products, stop searching
                
                # For RECOMMEND, look for recommended product
                elif intent == 'RECOMMEND':
                    state.active_intent = 'RECOMMEND'
                    # Get from metadata if available
                    if metadata.get('recommended_product'):
                        state.recommended_product = metadata.get('recommended_product')
                    else:
                        # Fallback: extract from text
                        content = bot_msg.get('content', '')
                        recommended = self._extract_recommended_product(content)
                        if recommended:
                            state.recommended_product = recommended
                    logging.info(f"[HistoryState] RECOMMEND: {state.recommended_product}")
                    break
                
                # For COMPARE, look for compared products
                elif intent == 'COMPARE':
                    state.active_intent = 'COMPARE'
                    # Get from metadata if available
                    if metadata.get('compared_products'):
                        state.compared_products = metadata.get('compared_products', [])
                    logging.info(f"[HistoryState] COMPARE: {state.compared_products}")
                    break
            
            # FALLBACK: Parse text (for old messages without metadata)
            else:
                content = bot_msg.get('content', '')
                self._analyze_last_bot_response(content, state)
                # If we found products via text parsing, stop
                if state.last_response_meta.get('product_names'):
                    logging.info(f"[HistoryState] Using text parsing fallback: {state.active_intent}")
                    break
        
        # Set active filters
        state.active_filters = {
            'bank': state.bank,
            'category': state.category
        }
        
        logging.info(f"[HistoryState] Final: Intent={state.active_intent}, Bank={state.bank}, Cat={state.category}, Products={len(state.last_response_meta.get('product_names', []))}")
        return state

    def _analyze_last_bot_response(self, content: str, state: ContextState):
        """Reverse-engineer what the bot just showed."""
        
        # Detect LIST
        if '📋' in content and 'total' in content.lower():
            state.active_intent = 'LIST'
            
            # Extract count: "(10 total)"
            match = re.search(r'\((\d+)\s+total\)', content)
            if match:
                state.last_response_meta['count_shown'] = int(match.group(1))
            
            # Extract product names from list
            # Format can be:
            # - With fee: "HDFC Regalia - Rs. 250"
            # - Without fee: "SBI Debit Card"
            # - Markdown: "1. **HDFC Regalia** - Rs. 250"
            products = []
            
            # First, try to extract bank name from the header "📋 SBI Debit Cards (10 total):"
            current_bank = None
            if state.bank:
                current_bank = state.bank
            else:
                header_match = re.search(r'📋\s*([A-Z]+)\s+', content)
                if header_match:
                    current_bank = header_match.group(1)
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('📋') or line.startswith('💡') or '(total)' in line.lower():
                    continue
                    
                # Remove markdown bold markers if present
                clean = line.replace('**', '')
                
                # Remove list markers (numbers, bullets) if present
                clean = re.sub(r'^(\d+\.|\d+\)|-|•|→)\s*', '', clean)
                clean = clean.strip()
                
                # Check if line contains a product
                if ' - ' in clean or ' – ' in clean:
                    # Has dash separator - split to get product name
                    split_match = re.split(r'\s+(-|–|:)\s+', clean, maxsplit=1)
                    if split_match and len(split_match) >= 1:
                        product_name = split_match[0].strip()
                        if product_name and len(product_name) > 3:
                            products.append(product_name)
                else:
                    # No dash - check if it looks like a product name
                    # Heuristics: starts with bank name, has multiple words, proper case
                    if current_bank and clean.startswith(current_bank):
                        # Likely a product name like "SBI Debit Card"
                        if len(clean) > 3 and len(clean) < 100:
                            products.append(clean)
                    elif re.match(r'^[A-Z][A-Za-z0-9\s\-&]+$', clean) and len(clean.split()) >= 2:
                        # Looks like a proper product name (capitalized, multiple words)
                        if len(clean) < 100:  # Sanity check
                            products.append(clean)
            
            state.last_response_meta['product_names'] = products
            logging.debug(f"[HistoryState] Extracted {len(products)} products: {products[:3]}...")

        # Detect COUNT ("There are 5 cards...")
        elif 'there are' in content.lower() and ('cards' in content.lower() or 'loans' in content.lower()):
            state.active_intent = 'COUNT'
            # Extract number
            match = re.search(r'there are (\d+)', content.lower())
            if match:
                state.last_response_meta['count_shown'] = int(match.group(1))

        # Detect EXPLAIN ("Here are the details for...")
        elif 'details for' in content.lower() or 'features of' in content.lower():
            state.active_intent = 'EXPLAIN'
            # Extract product name if possible
            # "Here are the details for HDFC Regalia:"
            match = re.search(r'details for ([^:]+)', content, re.IGNORECASE)
            if match:
                state.last_response_meta['product_explained'] = match.group(1).strip()

        # Detect COMPARE ("Comparison of...")
        elif 'comparison' in content.lower() or ' vs ' in content.lower():
            state.active_intent = 'COMPARE'

        # Detect RECOMMEND ("Recommendations: ...")
        elif 'recommendation' in content.lower() or 'suggest' in content.lower() or 'best' in content.lower() or 'might be' in content.lower():
            state.active_intent = 'RECOMMEND'
            # Heuristic 1: Look for bolded product name "**Product Name**"
            match = re.search(r'\*\*([A-Za-z0-9\s\-\.]+?)\*\*', content)
            if match:
                state.last_response_meta['recommended_product'] = match.group(1).strip()
            else:
                # Heuristic 2: Look for "the X might be" or "X is a great"
                match = re.search(r'the ([A-Z][A-Za-z0-9\s]+?(?:Card|Loan|Account))\s+(?:might|is|would|could)', content)
                if match:
                    state.last_response_meta['recommended_product'] = match.group(1).strip()
                else:
                    # Heuristic 3: Look for bullet points
                    match = re.search(r'[\d\.\-•]\s*([A-Za-z0-9\s]+?)(?:\s-|\n|:)', content)
                    if match:
                        state.last_response_meta['recommended_product'] = match.group(1).strip()

    def _extract_bank(self, content: str) -> Optional[str]:
        for bank in self.banks:
            if bank.lower() in content:
                return bank
        return None

    def _extract_category(self, content: str) -> Optional[str]:
        # Dynamic patterns
        patterns = self._build_category_patterns()
        for pattern, cat in patterns:
            if re.search(pattern, content):
                return cat
        return None

    def _extract_recommended_product(self, content: str) -> Optional[str]:
        """Extract the recommended product name from RECOMMEND responses."""
        # Heuristic 1: Look for bolded product name "**Product Name**"
        match = re.search(r'\*\*([A-Za-z0-9\s\-\.]+?)\*\*', content)
        if match:
            product = match.group(1).strip()
            # Filter out common non-product bold text
            if len(product) > 5 and not product.lower().startswith(('note', 'consider', 'important')):
                return product
        
        # Heuristic 2: "would be the X Card/Loan" or "likely be the X Card"
        match = re.search(r'(?:would|likely|probably)\s+be\s+the\s+([A-Z][A-Za-z0-9\s]+?(?:Card|Loan|Account))', content)
        if match:
            return match.group(1).strip()
        
        # Heuristic 3: "the X might be" or "X is a great"
        match = re.search(r'the ([A-Z][A-Za-z0-9\s]+?(?:Card|Loan|Account))\s+(?:might|is|would|could)', content)
        if match:
            return match.group(1).strip()
        
        # Heuristic 4: Look for bullet points
        match = re.search(r'[\d\.\-•]\s*([A-Za-z0-9\s]+?)(?:\s-|\n|:)', content)
        if match:
            return match.group(1).strip()
        
        return None

    # === DATA HELPERS (Duplicated from smart_router/config to avoid circular deps) ===
    # Ideally should be in a separate src.data_utils module
    
    def _get_supported_banks(self) -> List[str]:
        global _supported_banks_cache
        if _supported_banks_cache: return _supported_banks_cache
        
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            res = db.execute_raw_query("SELECT DISTINCT bank_name FROM products WHERE bank_name IS NOT NULL")
            _supported_banks_cache = [r['bank_name'] for r in res] or ['SBI', 'HDFC']
        except:
            _supported_banks_cache = ['SBI', 'HDFC']
        return _supported_banks_cache

    def _get_supported_categories(self) -> List[str]:
        global _supported_categories_cache
        if _supported_categories_cache: return _supported_categories_cache
        
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            res = db.execute_raw_query("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
            _supported_categories_cache = [r['category'] for r in res] or ['Credit Card', 'Loan']
        except:
            _supported_categories_cache = ['Credit Card', 'Loan']
        return _supported_categories_cache

    def _build_category_patterns(self) -> List[Tuple[str, str]]:
        patterns = []
        for cat in self.categories:
            cat_lower = cat.lower()
            patterns.append((rf'\b{cat_lower}', cat))
            # Partial: "credit" -> "Credit Card"
            words = cat_lower.split()
            if len(words) > 1:
                patterns.append((rf'\b{words[0]}\b', cat))
            # Plural: "loans" -> "Loan"
            if not cat_lower.endswith('s'):
                patterns.append((rf'\b{cat_lower}s\b', cat))
        return patterns
