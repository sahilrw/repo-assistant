"""Vector store wrapper (Chroma). Owns the embedding model and the collection."""

import os
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

embedder = SentenceTransformer("all-MiniLM-L6-v2")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

chroma_client = chromadb.PersistentClient(path=".chroma")
collection = chroma_client.get_or_create_collection("repo")

_bm25 = None
_corpus = None

def reset():
    global _bm25, _corpus, collection
    
    try:
        chroma_client.delete_collection("repo")
    except Exception:
        pass
        
    collection = chroma_client.get_or_create_collection("repo")
    _bm25 = None
    _corpus = None

def _ensure_bm25():
    global _bm25, _corpus
    if _bm25 is None:
        data = collection.get(include=["documents", "metadatas"])
        _corpus = list(zip(data["ids"], data["documents"], data["metadatas"]))
        tokenized_corpus = [text.lower().split() for _, text, _ in _corpus]
        _bm25 = BM25Okapi(tokenized_corpus)

def add_stream(ids: list, texts: list, metadatas: list, batch: int = 64):
    global _bm25, _corpus
    total = len(ids)
    for i in range(0, total, batch):
        embeddings = embedder.encode(texts[i:i+batch]).tolist()
        collection.upsert(
            ids=ids[i:i+batch],
            embeddings=embeddings,
            documents=texts[i:i+batch],
            metadatas=metadatas[i:i+batch],
        )
        yield min(i + batch, total), total
    _bm25 = None
    _corpus = None

def add(ids: list, texts: list, metadatas: list):
    for _ in add_stream(ids, texts, metadatas):
        pass


def all_paths():
    data = collection.get(include=["metadatas"])
    return sorted({m["path"] for m in data["metadatas"]})

def search(query: str, k: int = 5):
    query_embeddings = embedder.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embeddings,
        n_results=k
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    return list(zip(ids, documents, metadatas))

def hybrid_search(query: str, k: int = 5) -> list:
    semantic_results = search(query, k=20)
    semantic_ranking = [item[0] for item in semantic_results]

    _ensure_bm25()
    tokenized_query = query.lower().split()
    bm25_scores = _bm25.get_scores(tokenized_query)

    top_corpus_indices = sorted(
        range(len(bm25_scores)),
        key=lambda i: bm25_scores[i],
        reverse=True
    )[:20]

    keyword_ranking = [_corpus[idx][0] for idx in top_corpus_indices]

    rrf_scores = {}
    constant = 60

    for ranking in [semantic_ranking, keyword_ranking]:
        for rank, item_id in enumerate(ranking):
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + 1.0 / (constant + rank)

    fused_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]

    lookup = {item_id: (text, meta) for item_id, text, meta in _corpus}

    if not lookup and semantic_results:
        lookup = {item[0]: (item[1], item[2]) for item in semantic_results}

    return [(uid, lookup[uid][0], lookup[uid][1]) for uid in fused_ids if uid in lookup]

def rerank(query: str, candidates: list, top_n: int = 3) -> list:
    if not candidates:
        return []
    pairs = [(query, text) for _, text, _ in candidates]

    scores = reranker.predict(pairs)
    ranked = sorted(zip(candidates, scores), key=lambda item: item[1], reverse=True)
    return [candidate for candidate, _ in ranked[:top_n]]