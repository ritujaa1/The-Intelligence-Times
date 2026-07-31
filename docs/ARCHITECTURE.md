# How It Works — Step by Step

A complete walkthrough of the system, from a company name to a typeset intelligence brief. Every step names the file and function that does the work, so you can read the code alongside this.

**Live app:** [theintelligencetimes.streamlit.app](https://theintelligencetimes.streamlit.app) · **The one-sentence version:** four specialist LLM agents each write a cited section of a competitive-intelligence brief, grounded in evidence they retrieve themselves from a vector database using hybrid search, then check each other for contradictions.

---

## The shape of the whole thing

```
company name
     │
     ▼
[1] INGEST ── NewsAPI + GitHub + arXiv + sample corpus     src/ingest.py
     │         → chunk (180w / 40 overlap)
     │         → embed (Pinecone hosted multilingual-e5-large, 1024-dim)
     │         → upsert into namespace "openai"
     │         → mirror chunks to data/chunk_store.json (for BM25)
     ▼
[2] FOUR AGENTS, each independently:                       src/agents.py
     │    a. generate 3 search queries          (Groq, temp 0.4)
     │    b. hybrid retrieve                     src/retrieval.py
     │         semantic (Pinecone) ─┐
     │         BM25 (local)         ├─→ RRF fuse → top 16
     │                              ─┘
     │    c. LLM-as-judge re-rank 16 → 6        (Groq, temp 0.0)
     │    d. write section citing [1][2]...     (Groq, temp 0.2)
     ▼
[3] CROSS-CHECK — one pass over all four sections, flag contradictions (temp 0.1)
     ▼
[4] SYNTHESIZE — executive summary + strategic recommendation (temp 0.3)
     ▼
[5] MEASURE — citation coverage + number fidelity            src/report.py
     ▼
[6] TYPESET — broadsheet HTML                                app/newsprint.py
```

Total: **14 Groq calls per brief** (4 agents × 3 calls, plus cross-check and synthesis), one Pinecone query per agent-query, and roughly 25 seconds end to end.

---

## Step 1 — Ingestion

**File:** `src/ingest.py` · **Entry:** `ingest(company, offline=False)`

Four sources, each degrading gracefully to nothing if unavailable:

| Source | Function | Needs a key? | Category tag |
|---|---|---|---|
| NewsAPI | `fetch_news` | Yes (free) | `news` |
| GitHub org repos | `fetch_github` | Optional (raises rate limit) | `tech` |
| arXiv | `fetch_arxiv` | No | `tech` |
| Bundled sample corpus | `load_sample` | No | mixed |

Every fetcher is wrapped in try/except inside `ingest()` — a dead API degrades the corpus, it never kills the run. If NewsAPI is down you still get GitHub and arXiv.

The **category tag** matters: it is stored as vector metadata and later lets each agent search only its own slice of the corpus (the Market Agent doesn't wade through GitHub repo descriptions).

**Real numbers from a live run** (`--company "OpenAI"`, no `--offline`):
```
Sample corpus: 9 docs
fetch_news:   20 docs
fetch_github: 15 docs
fetch_arxiv:  10 docs
Total chunks: 56
```

### Chunking

`chunk_text()` — 180-word windows with 40-word overlap (`CHUNK_WORDS`, `CHUNK_OVERLAP` in `src/config.py`). ~240 tokens per chunk: large enough to carry a claim with its context, small enough that a retrieved chunk is mostly signal. The overlap prevents a fact from being severed at a boundary.

### Embedding and storage

`src/vectors.py: embed_passages()` calls **Pinecone's hosted inference API** with `multilingual-e5-large` (1024 dimensions). This is the design decision that keeps the laptop empty: no PyTorch, no sentence-transformers, no model download. The repo is ~5MB of pure Python.

Vectors go into a per-company **namespace** (`slugify("OpenAI") → "openai"`). Namespaces give hard isolation between companies inside a single free-tier index — a query for OpenAI can never accidentally retrieve Anthropic's chunks.

> **Gotcha worth knowing:** the namespace comes from the typed name, so `"OpenAI"` and `"Open AI"` produce two separate archives (`openai`, `open-ai`). Spelling is identity.

Chunks are also mirrored to `data/chunk_store.json` — that local copy is what BM25 searches, since Pinecone stores vectors, not a keyword index. This file is committed to the repo on purpose so a fresh deploy has working archives immediately.

---

## Step 2 — The four agents

**File:** `src/agents.py` · **Entry:** `analyze_company(company)` → `run_agent(name, spec, company)`

```python
AGENTS = {
    "Research Agent":   {"category": "news",   "focus": "recent news, funding, partnerships, ..."},
    "Technology Agent": {"category": "tech",   "focus": "technology stack, open-source activity, ..."},
    "Market Agent":     {"category": "market", "focus": "pricing, customer segments, market share, ..."},
    "Threat Agent":     {"category": "threat", "focus": "weaknesses, risks, emerging competitors, ..."},
}
```

The agents are not four different models or four different prompts-with-personalities. What actually makes them specialists is **two things**: the category filter that scopes their retrieval, and the focus string that shapes both their query generation and their writing brief. That's a deliberately cheap abstraction, and it's most of the value.

### 2a. Query generation

Each agent writes its own search queries rather than reusing the company name:

```python
queries = llm_json(
    f'You are the {name} analyzing the company "{company}". '
    f"Your focus: {spec['focus']}. Generate 3 short, diverse search queries...",
    temperature=0.4, max_tokens=200,
).get("queries", [...])[:3]
```

Temperature 0.4 — high enough for genuine diversity between the three queries, low enough to stay on topic. The `.get(..., fallback)` means a malformed JSON response degrades to a single sensible query instead of crashing.

Real generated queries from the Technology Agent: *"OpenAI tech stack architecture"*, *"OpenAI GitHub open-source contributions"*, *"OpenAI research papers on transformer models"*.

### 2b. Hybrid retrieval

**File:** `src/retrieval.py` · **Entry:** `hybrid_retrieve(queries, namespace, category)`

For each of the 3 queries, two searches run:

**Semantic** (`semantic_search`) — embeds the query, queries Pinecone with a metadata filter on category, returns top 8. Catches paraphrase: *"how do they make money"* matches a passage about pricing tiers.

**BM25** (`bm25_search`) — classic keyword ranking over the local chunk store, top 8. Catches exact tokens that embeddings blur: `$300M`, `GPT-5.6`, a specific product name. The index is built lazily and cached per namespace in `_bm25_cache`.

**Why both?** They fail in opposite directions. Vector search is strong on meaning and weak on rare literals; BM25 is the reverse. Numeric and product-name queries — exactly what competitive intelligence is full of — are where BM25 rescues the vector search.

### 2c. Reciprocal Rank Fusion

```python
def rrf_merge(result_lists, k=60):
    for results in result_lists:
        for rank, r in enumerate(results):
            fused[r["id"]]["rrf"] += 1.0 / (k + rank + 1)
```

Six ranked lists (3 queries × 2 retrievers) collapse into one. **The key property: RRF only reads ranks, never scores.** Cosine similarity (0–1, compressed near the top) and BM25 scores (unbounded, corpus-dependent) live on incomparable scales — any weighted average of them needs calibration that breaks when the corpus changes. RRF sidesteps the problem entirely and is four lines of code. The constant `k=60` is the standard damping value from the original paper; it stops rank-1 results from dominating so completely that agreement between retrievers stops mattering.

A chunk that appears in several lists accumulates contributions — so **consensus across retrievers and across the agent's three queries is what floats a chunk to the top.**

### 2d. LLM-as-judge re-ranking

```python
scores = llm_json(f"Query: {query}\n\nScore each passage 0-100 for how useful "
                  f"it is to answer the query.\n\n{numbered}...", temperature=0.0)
```

The top 16 fused candidates go to Groq in **one batched call**, which scores each 0–100; the top 6 survive (`TOP_K_FINAL`). Temperature 0.0 for reproducibility.

This is one extra call per agent (4 per brief) and it measurably sharpens the evidence set — RRF is good at recall, the judge is good at precision. Note the failure handling: if the judge call fails or returns garbage, `rerank()` catches it and **falls back to RRF order** rather than losing the brief. Re-rank scores are surfaced in the UI (`85/100`) so you can see the judge's opinion.

There's also a **retrieval fallback** in `run_agent`: if the category-filtered search returns fewer than 3 chunks, it re-runs unfiltered across all categories. A thin corpus degrades the specialization rather than producing an empty section.

### 2e. Grounded writing

```python
GROUNDING_RULES = (
    "Use ONLY the numbered evidence passages provided. Cite every factual claim "
    "with [n] markers. If the evidence does not cover something, write "
    "'No evidence found' for that point instead of guessing. Never invent numbers."
)
```

Evidence is injected as a numbered list; the model writes 4–7 bullets at temperature 0.2. The escape hatch matters as much as the prohibition — *"No evidence found on specific hiring numbers"* is a line that actually appears in real output, and it is the model doing the right thing instead of inventing a figure.

---

## Step 3 — Cross-check (the "debate")

`cross_check()` takes all four finished sections and asks one question: where do these contradict each other?

This is a deliberately lightweight take on multi-agent debate — **one synthesis-level pass instead of multi-round agent-to-agent messaging.** It catches the thing that actually matters (Research citing 45% valuation growth while Threat cites margin compression and 11% attrition) at the cost of a single call instead of dozens.

Real output:
> *"The Research Agent section mentions OpenAI plans to hire across engineering, implying growth [1]. In contrast, the Threat Agent section notes OpenAI faces talent attrition at 11% [4], which could be a contradictory signal."*

The honest upgrade path, if asked: turn detected conflicts into targeted re-query loops with a budget cap.

---

## Step 4 — Synthesis

`synthesize()` reads the four sections plus the conflict notes and produces an **executive summary** and a **strategic recommendation** written from the perspective of a competitor. Instructed to ground everything in the sections and add no new facts — the synthesizer summarizes, it does not research.

---

## Step 5 — Groundedness metrics

**File:** `src/report.py` · **Function:** `groundedness(report)`

Two cheap, honest checks computed on every single brief:

**Citation coverage** — the fraction of substantive bullets carrying a `[n]` marker. Measures whether the model followed the citation discipline.

**Number fidelity** — every number in the prose is extracted and checked for existence in the retrieved evidence text:

```python
evidence_nums = set(NUM_RE.findall(evidence_text))
for n in NUM_RE.findall(re.sub(r"\[\d+\]", "", line)):
    nums += 1
    if n in evidence_nums:
        grounded_nums += 1
```

This is the sharpest tool in the box and it's about ten lines. Invented revenue figures, made-up market shares, and hallucinated growth rates all fail it, because a fabricated number by definition does not appear in the source passages. Citation markers are stripped first so `[3]` isn't counted as the number 3.

**Be honest about what it is:** a proxy, not ground truth. It cannot catch a *correct* number attached to a *wrong* claim, and a number legitimately derived by arithmetic would be flagged. It is a cheap smoke detector, not a fire inspection. Reported scores on real runs sit at **76–80%** — and the gap from 100% is mostly rephrased and derived figures, which is worth saying out loud rather than tuning away.

**Measured on real runs:**

| Run | Citation coverage | Number fidelity | Sources | Bullets | Time |
|---|---|---|---|---|---|
| CLI, sample corpus | 79% | 79% | 21 | 29 | 25.8s |
| Web UI, live corpus | 76% | 80% | 24 | 29 | 24.8s |
| Deployed (Streamlit Cloud) | — | — | — | — | 26.4s |

Per-agent latency, real: retrieval 1,900–5,500ms, re-rank 310–620ms.

---

## Step 6 — Typesetting

**File:** `app/newsprint.py`

The presentation layer is deliberately **free of Streamlit imports** — it is pure functions from a report dict to HTML. That separation buys two things: the Streamlit app (`app/streamlit_app.py`) and the standalone exporter (`src/export_html.py`) share one source of truth for the design, and a saved brief can be rendered with no app and no API calls.

```bash
python -m src.export_html --company "OpenAI"   # → standalone HTML, print to PDF
```

The layout is a broadsheet in the Economic Times' salmon newsprint: masthead and dateline, a lead story with a drop cap in two justified columns, four desk sections with column rules, red citation superscripts, agate-type source footnotes, a double-ruled cross-examination box, and a metrics ticker.

---

## Module map

| File | Role |
|---|---|
| `src/config.py` | All tuning constants and secrets. Reads env vars first, falls back to `st.secrets` for Streamlit Cloud |
| `src/vectors.py` | Pinecone index bootstrap + hosted embeddings; Groq wrapper with retry/backoff and a JSON mode that strips code fences |
| `src/ingest.py` | Fetch → chunk → embed → upsert; writes the BM25 mirror |
| `src/retrieval.py` | Semantic + BM25 + RRF + LLM-as-judge re-rank |
| `src/agents.py` | The four agents, cross-check, synthesis |
| `src/report.py` | CLI entry, text rendering, groundedness metrics |
| `src/export_html.py` | Saved brief → standalone newspaper page |
| `app/newsprint.py` | Stylesheet + typesetting functions (no Streamlit) |
| `app/streamlit_app.py` | Web app: commissioning desk, live ingestion, printed edition |

## Tuning knobs (`src/config.py`)

```python
CHUNK_WORDS = 180        # chunk size
CHUNK_OVERLAP = 40       # prevents facts being cut at boundaries
TOP_K_SEMANTIC = 8       # per query, per retriever
TOP_K_BM25 = 8
TOP_K_FINAL = 6          # evidence passages per agent after re-ranking
GROQ_MODEL = "llama-3.3-70b-versatile"
EMBED_MODEL = "multilingual-e5-large"   # 1024-dim, Pinecone-hosted
```

## Operational notes

**Groq free tier: 100,000 tokens/day.** A brief costs roughly 25–30K tokens, so **~3–4 briefs per day** before requests start returning HTTP 429. The app surfaces this as a "Corrections & Clarifications" notice rather than a stack trace. This is the binding constraint on a public demo — the obvious fix is caching briefs per company so repeat visitors read the archive instead of re-running the presses.

**Retry behavior:** `llm()` retries 3 times with linear backoff (5s, 10s). That handles per-minute rate limits; it cannot help with a daily cap.

**Secrets on Streamlit Cloud:** the platform only mirrors secrets into `os.environ` after `st.secrets` is first accessed, so `src/config.py` deliberately checks env vars first and falls back to `st.secrets`. Secrets must be valid TOML — quoted values — or the whole file is rejected silently and the app behaves as though no keys exist at all.

**Sequential by design:** agents run one after another to stay inside free-tier rate limits. They are embarrassingly parallel and would drop total time to roughly the slowest agent (~7s) with asyncio and a paid tier.

## Honest limitations

- The bundled sample corpus is **synthetic** — invented numbers for a reliable offline demo. Live mode ingests real data. The architecture is identical either way.
- Groundedness metrics are proxies, not a labeled evaluation. There is no relevance-judgment set, so no true precision@k.
- BM25 loads the chunk store into process memory — fine for thousands of chunks, wrong past ~1M.
- `fetch_github` guesses the org name by slugifying the company, so it misses when the GitHub org differs from the company name.
- One index, many namespaces: clean isolation, but a per-tenant deployment would want separate indexes.
