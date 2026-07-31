"""
Hybrid retrieval: Pinecone semantic search + local BM25 keyword search,
merged with Reciprocal Rank Fusion, then re-ranked by Groq (LLM-as-judge).
"""

import json
import time

from rank_bm25 import BM25Okapi

from src.config import (CHUNK_STORE, TOP_K_BM25, TOP_K_FINAL, TOP_K_SEMANTIC)
from src.vectors import embed_query, get_index, llm_json

_bm25_cache: dict = {}


def _bm25_for(namespace: str):
    if namespace not in _bm25_cache:
        store = json.loads(CHUNK_STORE.read_text()) if CHUNK_STORE.exists() else {}
        chunks = store.get(namespace, [])
        tokenized = [c["text"].lower().split() for c in chunks] or [["placeholder"]]
        _bm25_cache[namespace] = (BM25Okapi(tokenized), chunks)
    return _bm25_cache[namespace]


def semantic_search(query: str, namespace: str, category: str | None = None,
                    k: int = TOP_K_SEMANTIC) -> list[dict]:
    flt = {"category": {"$eq": category}} if category else None
    res = get_index().query(vector=embed_query(query), top_k=k, namespace=namespace,
                            include_metadata=True, filter=flt)
    return [{"id": m["id"], "score": m["score"], **m["metadata"]}
            for m in res["matches"]]


def bm25_search(query: str, namespace: str, category: str | None = None,
                k: int = TOP_K_BM25) -> list[dict]:
    bm25, chunks = _bm25_for(namespace)
    if not chunks:
        return []
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    out = []
    for chunk, score in ranked:
        if category and chunk["category"] != category:
            continue
        out.append({**chunk, "score": float(score)})
        if len(out) >= k:
            break
    return out


def rrf_merge(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: robust way to merge rankings from different scorers."""
    fused: dict[str, dict] = {}
    for results in result_lists:
        for rank, r in enumerate(results):
            entry = fused.setdefault(r["id"], {**r, "rrf": 0.0})
            entry["rrf"] += 1.0 / (k + rank + 1)
    return sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)


def rerank(query: str, candidates: list[dict], top_k: int = TOP_K_FINAL) -> list[dict]:
    """LLM-as-judge re-ranking: score each candidate chunk 0-100 for relevance."""
    if len(candidates) <= top_k:
        for c in candidates:
            c["rerank_score"] = None
        return candidates
    numbered = "\n\n".join(f"[{i}] {c['text'][:400]}" for i, c in enumerate(candidates))
    try:
        scores = llm_json(
            f"Query: {query}\n\nScore each passage 0-100 for how useful it is to "
            f"answer the query.\n\n{numbered}\n\n"
            f'Return JSON: {{"scores": [{{"index": 0, "score": 85}}, ...]}}',
            temperature=0.0, max_tokens=600)
        for s in scores.get("scores", []):
            i = int(s["index"])
            if 0 <= i < len(candidates):
                candidates[i]["rerank_score"] = float(s["score"])
    except Exception as e:
        print(f"  Re-rank failed ({e}); falling back to RRF order")
    ranked = sorted(candidates,
                    key=lambda c: c.get("rerank_score") or c.get("rrf", 0), reverse=True)
    return ranked[:top_k]


def hybrid_retrieve(queries: list[str], namespace: str, category: str | None = None,
                    top_k: int = TOP_K_FINAL) -> tuple[list[dict], dict]:
    """Full pipeline for a set of queries: semantic + BM25 -> RRF -> LLM re-rank.

    Returns (top chunks, stats dict).
    """
    t0 = time.time()
    all_lists = []
    for q in queries:
        all_lists.append(semantic_search(q, namespace, category))
        all_lists.append(bm25_search(q, namespace, category))
    merged = rrf_merge(all_lists)
    t_retrieve = time.time() - t0

    t1 = time.time()
    top = rerank(" | ".join(queries), merged[:16], top_k=top_k)
    stats = {"queries": len(queries), "candidates": len(merged),
             "retrieval_ms": round(t_retrieve * 1000),
             "rerank_ms": round((time.time() - t1) * 1000)}
    return top, stats
