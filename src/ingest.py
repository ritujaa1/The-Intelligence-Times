"""
Data ingestion: pull documents about a company from free sources, chunk them,
embed with Pinecone's hosted model, and upsert into the vector index.

Sources (all free):
  - NewsAPI (needs free key; skipped gracefully if absent)
  - GitHub API (org repos; token optional but raises rate limits)
  - arXiv API (no key needed)
  - data/sample_corpus.json fallback (works fully offline, for instant demos)

Also writes every chunk to data/chunk_store.json so BM25 keyword search can
run locally without extra infrastructure.

Usage:
    python -m src.ingest --company "OpenAI"
    python -m src.ingest --company "OpenAI" --offline   # sample corpus only
"""

import argparse
import json
import re
import time

import requests

from src.config import (CATEGORIES, CHUNK_OVERLAP, CHUNK_STORE, CHUNK_WORDS,
                        DATA_DIR, GITHUB_TOKEN, NEWSAPI_KEY, require)
from src.vectors import get_index, embed_passages


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text.strip()] if text.strip() else []
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        start += size - overlap
    return chunks


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Free data sources
# ---------------------------------------------------------------------------

def fetch_news(company: str) -> list[dict]:
    if not NEWSAPI_KEY:
        print("  NewsAPI key not set — skipping live news")
        return []
    r = requests.get(
        "https://newsapi.org/v2/everything",
        params={"q": f'"{company}"', "language": "en", "pageSize": 20,
                "sortBy": "publishedAt", "apiKey": NEWSAPI_KEY},
        timeout=20,
    )
    r.raise_for_status()
    docs = []
    for a in r.json().get("articles", []):
        text = " ".join(filter(None, [a.get("title"), a.get("description"), a.get("content")]))
        if len(text.split()) < 20:
            continue
        docs.append({"category": "news", "title": a.get("title", "news article"),
                     "source": a.get("url", "NewsAPI"), "text": text})
    return docs


def fetch_github(company: str) -> list[dict]:
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    r = requests.get(f"https://api.github.com/orgs/{slugify(company)}/repos",
                     params={"sort": "updated", "per_page": 15},
                     headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"  GitHub org '{slugify(company)}' not found — skipping")
        return []
    docs = []
    for repo in r.json():
        text = (f"Repository {repo['name']}: {repo.get('description') or 'no description'}. "
                f"Language: {repo.get('language')}. Stars: {repo.get('stargazers_count')}. "
                f"Forks: {repo.get('forks_count')}. Open issues: {repo.get('open_issues_count')}. "
                f"Last updated: {repo.get('updated_at')}.")
        docs.append({"category": "tech", "title": f"GitHub: {repo['name']}",
                     "source": repo.get("html_url", "github.com"), "text": text})
    return docs


def fetch_arxiv(company: str) -> list[dict]:
    r = requests.get("http://export.arxiv.org/api/query",
                     params={"search_query": f'all:"{company}"', "max_results": 10},
                     timeout=20)
    if r.status_code != 200:
        return []
    entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.S)
    docs = []
    for e in entries:
        title = re.search(r"<title>(.*?)</title>", e, re.S)
        summary = re.search(r"<summary>(.*?)</summary>", e, re.S)
        link = re.search(r"<id>(.*?)</id>", e, re.S)
        if title and summary:
            docs.append({"category": "tech",
                         "title": f"arXiv: {title.group(1).strip()[:90]}",
                         "source": link.group(1).strip() if link else "arxiv.org",
                         "text": re.sub(r"\s+", " ", summary.group(1)).strip()})
    return docs


def load_sample(company: str) -> list[dict]:
    path = DATA_DIR / "sample_corpus.json"
    if not path.exists():
        return []
    corpus = json.loads(path.read_text())
    return corpus.get(company, corpus.get(slugify(company), []))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def ingest(company: str, offline: bool = False) -> None:
    require("PINECONE_API_KEY")
    print(f"Ingesting data for: {company}")

    docs = load_sample(company)
    if docs:
        print(f"  Sample corpus: {len(docs)} docs")
    if not offline:
        for fn in (fetch_news, fetch_github, fetch_arxiv):
            try:
                fetched = fn(company)
                print(f"  {fn.__name__}: {len(fetched)} docs")
                docs += fetched
            except Exception as e:
                print(f"  {fn.__name__} failed ({e}) — continuing")

    if not docs:
        raise SystemExit("No documents found. Add the company to data/sample_corpus.json "
                         "or set NEWSAPI_KEY / check the GitHub org name.")

    # Chunk
    namespace = slugify(company)
    chunks = []
    for d_i, d in enumerate(docs):
        for c_i, chunk in enumerate(chunk_text(d["text"])):
            chunks.append({"id": f"{namespace}-{d_i}-{c_i}",
                           "category": d["category"] if d["category"] in CATEGORIES else "news",
                           "title": d["title"], "source": d["source"], "text": chunk})
    print(f"  Total chunks: {len(chunks)}")

    # Embed + upsert in batches (Pinecone hosted embeddings — nothing local)
    index = get_index()
    for i in range(0, len(chunks), 50):
        batch = chunks[i:i + 50]
        vectors = embed_passages([c["text"] for c in batch])
        index.upsert(
            vectors=[{"id": c["id"], "values": v,
                      "metadata": {k: c[k] for k in ("category", "title", "source", "text")}}
                     for c, v in zip(batch, vectors)],
            namespace=namespace,
        )
        print(f"  Upserted {min(i + 50, len(chunks))}/{len(chunks)}")
        time.sleep(0.3)

    # Local chunk store for BM25
    store = json.loads(CHUNK_STORE.read_text()) if CHUNK_STORE.exists() else {}
    store[namespace] = chunks
    CHUNK_STORE.write_text(json.dumps(store))
    print(f"✓ Done. Namespace '{namespace}' ready with {len(chunks)} chunks.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--company", required=True)
    p.add_argument("--offline", action="store_true", help="sample corpus only")
    args = p.parse_args()
    ingest(args.company, offline=args.offline)
