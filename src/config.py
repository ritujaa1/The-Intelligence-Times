"""Central configuration — reads all secrets from .env. $0 stack."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

def _secret(name: str) -> str:
    """Env var first (local .env); fall back to Streamlit secrets (cloud).

    Streamlit Cloud only mirrors secrets into os.environ once st.secrets is
    accessed, so a plain os.getenv would miss them.
    """
    val = os.getenv(name, "")
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


# --- Keys (all free tiers) ---
GROQ_API_KEY = _secret("GROQ_API_KEY")
PINECONE_API_KEY = _secret("PINECONE_API_KEY")
NEWSAPI_KEY = _secret("NEWSAPI_KEY")          # optional
GITHUB_TOKEN = _secret("GITHUB_TOKEN")        # optional

# --- Models ---
# Groq free tier. If this model is deprecated, list current ones with:
#   python -c "from groq import Groq; import src.config as c; print([m.id for m in Groq(api_key=c.GROQ_API_KEY).models.list().data])"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Pinecone hosted embedding model (free tier includes inference API).
EMBED_MODEL = os.getenv("EMBED_MODEL", "multilingual-e5-large")
EMBED_DIM = 1024

# --- Pinecone index ---
INDEX_NAME = os.getenv("INDEX_NAME", "competitive-intelligence")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# --- Retrieval ---
CHUNK_WORDS = 180          # ~240 tokens per chunk
CHUNK_OVERLAP = 40
TOP_K_SEMANTIC = 8
TOP_K_BM25 = 8
TOP_K_FINAL = 6            # per agent after re-ranking

CATEGORIES = ["news", "tech", "market", "threat"]

CHUNK_STORE = DATA_DIR / "chunk_store.json"   # local copy for BM25


def require(*names: str) -> None:
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}. "
                         f"Copy .env.example to .env and fill these in.")
