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
        Ingests a list of FAQ dictionaries.
        Expected format:
        [
            {'bank_name': 'SBI', 'category': 'Loans', 'question': '...', 'answer': '...'},
            ...
        ]
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
            
            # Content to embed: "Question: ... Answer: ..." or just Question?
            # Usually embedding the Question is best for retrieval, 
            # but sometimes mixing Q and A helps. 
            # Let's embed "Question: {q} \n Answer: {a}" to capture full context.
            # OR just Question for finding the right FAQ.
            # Let's try: Question + Answer context.
            text_content = f"Question: {faq.get('question', '')}\nAnswer: {faq.get('answer', '')}"
            documents.append(text_content)
            
            # Metadata for filtering
            metadatas.append({
                "bank_name": faq.get("bank_name", "Unknown"),
                "category": faq.get("category", "General"),
                "question": faq.get("question", ""), 
                "answer": faq.get("answer", "") # Store answer in metadata for retrieval display
            })
            
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

    def query_faqs(self, user_query, bank_filter=None, n_results=3):
        """
        Searches for relevant FAQs.
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
            where=where_clause
        )
        
        # Parse results
        parsed_results = []
        if results['metadatas'] and len(results['metadatas']) > 0:
            for meta in results['metadatas'][0]:
                parsed_results.append(meta)
                
        return parsed_results

    def reset_collection(self):
        """Clears the collection - useful for re-ingestion"""
        self.client.delete_collection("bank_faqs")
        self.collection = self.client.get_or_create_collection(
            name="bank_faqs",
            embedding_function=self.embedding_fn
        )
