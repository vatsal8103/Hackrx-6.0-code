# vector_store.py (CREATE IN ROOT DIRECTORY)
import faiss
import numpy as np
import pickle
import os
from typing import List, Dict
from sentence_transformers import SentenceTransformer

class FAISSVectorStore:
    def __init__(self, dimension: int = 384, index_path: str = "data/faiss_index"):
        self.dimension = dimension
        self.index_path = index_path
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata = []
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Load existing index if available
        self.load_index()
    
    def add_documents(self, texts: List[str], metadata: List[Dict] = None):
        if not texts:
            return
            
        embeddings = self.model.encode(texts)
        self.index.add(embeddings.astype('float32'))
        
        if metadata is None:
            metadata = [{"text": text, "id": len(self.metadata) + i} for i, text in enumerate(texts)]
        
        self.metadata.extend(metadata)
        self.save_index()
    
    def similarity_search(self, query: str, k: int = 5):
        if self.index.ntotal == 0:
            return []
            
        query_vector = self.model.encode([query]).astype('float32')
        distances, indices = self.index.search(query_vector, min(k, self.index.ntotal))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata) and idx >= 0:
                results.append({
                    'content': self.metadata[idx],
                    'similarity': 1 / (1 + distances[0][i]),
                    'distance': distances[0][i]
                })
        return results
    
    def save_index(self):
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            faiss.write_index(self.index, f"{self.index_path}.index")
            with open(f"{self.index_path}_metadata.pkl", "wb") as f:
                pickle.dump(self.metadata, f)
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def load_index(self):
        try:
            if os.path.exists(f"{self.index_path}.index"):
                self.index = faiss.read_index(f"{self.index_path}.index")
                with open(f"{self.index_path}_metadata.pkl", "rb") as f:
                    self.metadata = pickle.load(f)
                print(f"Loaded index with {self.index.ntotal} vectors")
        except Exception as e:
            print(f"Could not load existing index: {e}")
