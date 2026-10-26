"""Thin wrappers around Pinecone (index + hosted embeddings) and Groq (LLM).

Using Pinecone's hosted embedding model means zero local ML dependencies —
no PyTorch, no model downloads. Everything heavy runs in the cloud.
"""

import json
import re
import time

from src.config import (EMBED_DIM, EMBED_MODEL, GROQ_API_KEY, GROQ_MODEL,
                        INDEX_NAME, PINECONE_API_KEY, PINECONE_CLOUD,
                        PINECONE_REGION)

_pc = None
_index = None
_groq = None


def _pinecone():
    global _pc
    if _pc is None:
        from pinecone import Pinecone
        _pc = Pinecone(api_key=PINECONE_API_KEY)
    return _pc


def get_index():
    """Return the Pinecone index, creating it (serverless, free tier) if needed."""
    global _index
    if _index is not None:
        return _index
    from pinecone import ServerlessSpec
    pc = _pinecone()
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"Creating Pinecone serverless index '{INDEX_NAME}'...")
        pc.create_index(name=INDEX_NAME, dimension=EMBED_DIM, metric="cosine",
                        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION))
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(2)
    _index = pc.Index(INDEX_NAME)
    return _index


def _embed(texts: list[str], input_type: str) -> list[list[float]]:
    res = _pinecone().inference.embed(
        model=EMBED_MODEL, inputs=texts, parameters={"input_type": input_type})
    out = []
    for item in res:
        out.append(item["values"] if isinstance(item, dict) else item.values)
    return out


def embed_passages(texts: list[str]) -> list[list[float]]:
    return _embed(texts, "passage")


def embed_query(text: str) -> list[float]:
    return _embed([text], "query")[0]


# ---------------------------------------------------------------------------
# Groq LLM
# ---------------------------------------------------------------------------

def llm(prompt: str, system: str = "", temperature: float = 0.2,
        max_tokens: int = 1200, retries: int = 3) -> str:
    """Single Groq chat completion with simple rate-limit retry."""
    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=GROQ_API_KEY)
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    # Reasoning models (gpt-oss) spend tokens thinking before answering:
    # keep thinking short and add headroom so answers aren't truncated.
    extra = {}
    if "gpt-oss" in GROQ_MODEL:
        extra = {"reasoning_effort": "low"}
        max_tokens += 2000
    for attempt in range(retries):
        try:
            resp = _groq.chat.completions.create(
                model=GROQ_MODEL, messages=messages,
                temperature=temperature, max_tokens=max_tokens, **extra)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"  Groq error ({e}); retrying in {wait}s...")
            time.sleep(wait)
    return ""


def llm_json(prompt: str, system: str = "", **kw) -> dict | list:
    """LLM call that must return JSON; strips code fences and parses."""
    raw = llm(prompt + "\n\nRespond with ONLY valid JSON. No prose, no markdown.",
              system=system, **kw)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    match = re.search(r"[\[{].*[\]}]", raw, re.S)
    return json.loads(match.group(0) if match else raw)
