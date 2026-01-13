import chromadb
from chromadb.utils import embedding_functions
import os
import uuid
from src.config import CHROMADB_DIR, EMBEDDING_MODEL, CHROMA_COLLECTION_NAME

class FAQVectorDB:
    def __init__(self):
        # Ensure directory exists
        os.makedirs(CHROMADB_DIR, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        
        # Use sentence-transformers for better quality embeddings
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

    def upsert_faqs(self, faqs_list):
        """
        Ingests a list of FAQ dictionaries with support for extra fields.
        
        Required format:
        [
            {'bank_name': 'SBI', 'category': 'Loans', 'question': '...', 'answer': '...'},
            ...
        ]
        
        Extra fields (optional):
        - Any additional fields are stored in metadata for filtering/display
        """
        if not faqs_list:
            return
            
        ids = []
        documents = []
        metadatas = []
        
        for faq in faqs_list:
            # unique ID
            doc_id = str(uuid.uuid4())
            ids.append(doc_id)
            
            # Content to embed: Question + Answer for full context
            text_content = f"Question: {faq.get('question', '')}\\nAnswer: {faq.get('answer', '')}"
            documents.append(text_content)
            
            # Build metadata - core fields + any extras
            metadata = {
                "bank_name": faq.get("bank_name", "Unknown"),
                "category": faq.get("category", "General"),
                "question": faq.get("question", ""), 
                "answer": faq.get("answer", "")
            }
            
            # Add extra fields if present
            if 'extra_fields' in faq:
                # Merge extra fields into metadata
                metadata.update(faq['extra_fields'])
            
            # Also capture any other top-level keys not in core fields
            core_keys = {'bank_name', 'category', 'question', 'answer', 'extra_fields'}
            for key, value in faq.items():
                if key not in core_keys and value is not None:
                    metadata[key] = str(value)
            
            metadatas.append(metadata)
            
        # Upsert in batches to avoid hitting limits
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end]
            )
            print(f"   -> Upserted batch {i} to {end}")

    def query_faqs(self, user_query, bank_filter=None, n_results=3, include_distances=False):
        """
        Searches for relevant FAQs.
        
        Args:
            user_query: The query string
            bank_filter: Optional filter by bank name
            n_results: Number of results to return
            include_distances: If True, returns similarity distances with results
        """
        where_clause = {}
        if bank_filter:
            where_clause["bank_name"] = bank_filter
            
        # If bank_filter is empty, pass None to where (chroma syntax)
        if not bank_filter:
            where_clause = None

        results = self.collection.query(
            query_texts=[user_query],
            n_results=n_results,
            where=where_clause,
            include=['metadatas', 'distances'] if include_distances else ['metadatas']
        )
        
        # Parse results
        parsed_results = []
        if results['metadatas'] and len(results['metadatas']) > 0:
            for i, meta in enumerate(results['metadatas'][0]):
                result_item = dict(meta)  # Copy metadata
                # Add distance/similarity if requested
                if include_distances and results.get('distances') and len(results['distances']) > 0:
                    # ChromaDB returns L2 distance - lower is more similar
                    # Convert to similarity: 1 / (1 + distance)
                    distance = results['distances'][0][i]
                    result_item['distance'] = distance
                    result_item['similarity'] = 1 / (1 + distance)
                parsed_results.append(result_item)
                
        return parsed_results

    def reset_collection(self):
        """Clears the collection - useful for re-ingestion"""
        self.client.delete_collection(CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )
