import numpy as np
from rank_bm25 import BM25Okapi
import re

class HybridRetriever:
    def __init__(self, vectorstore, chunks, k=10):
        self.vectorstore = vectorstore
        self.k = k
        self.chunks = chunks
        tokenized = [c.page_content.lower().split() for c in chunks]
        self.bm25 = BM25Okapi(tokenized)
    
    def _determine_alpha(self, query):
        query_lower = query.lower()
        has_specific = bool(re.search(r'(pojk|seojk|uu)\s*\d+', query_lower))
        has_pasal = 'pasal' in query_lower
        return 0.3 if (has_specific or has_pasal) else 0.6
    
    def reciprocal_rank_fusion(self, dense, sparse_idx, alpha=0.5, k=60):
        scores = {}
        doc_map = {}
        
        def doc_id(doc):
            return f"{doc.metadata.get('source')}::{doc.metadata.get('page')}"
        
        for rank, doc in enumerate(dense):
            did = doc_id(doc)
            scores[did] = scores.get(did, 0) + alpha * (1 / (k + rank + 1))
            doc_map[did] = doc
        
        for rank, idx in enumerate(sparse_idx):
            doc = self.chunks[idx]
            did = doc_id(doc)
            scores[did] = scores.get(did, 0) + (1 - alpha) * (1 / (k + rank + 1))
            doc_map[did] = doc
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[did] for did, _ in ranked]
    
    def retrieve(self, query):
        alpha = self._determine_alpha(query)
        dense = self.vectorstore.similarity_search(query, k=self.k)
        sparse_scores = self.bm25.get_scores(query.lower().split())
        sparse_idx = np.argsort(sparse_scores)[::-1][:self.k]
        return self.reciprocal_rank_fusion(dense, sparse_idx, alpha=alpha)[:self.k]