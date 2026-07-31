# Resume Bullets & Interview Guide — Agentic RAG Competitive Intelligence

## Resume

**Project title line:**
**Agentic RAG Competitive Intelligence System** | Python, Pinecone, Groq, Hybrid Retrieval, Multi-Agent
*GitHub: <link> | Live demo: <link>*

**Bullets (fill metrics from a real run — the app prints them):**

- Architected a multi-agent RAG system where 4 specialist agents (research, technology, market, threat) autonomously generate queries, retrieve evidence from Pinecone via hybrid search (semantic + BM25 fused with Reciprocal Rank Fusion), and write source-attributed intelligence briefs
- Implemented LLM-as-judge re-ranking (Groq Llama 3.3 70B) over fused candidates and a conflict cross-check pass between agents, with [X]% citation coverage and [Y]% number fidelity (custom hallucination metric) on generated reports
- Built a zero-infrastructure ingestion pipeline (NewsAPI, GitHub, arXiv) with chunking, Pinecone-hosted embeddings (multilingual-e5-large), and per-company namespace isolation; end-to-end brief generation in [Z]s at $0/month running cost
- Shipped a Streamlit demo exposing per-agent sources, re-rank scores, retrieval latency, and groundedness metrics

**Skills line:** `Agentic RAG` · `Multi-Agent Orchestration` · `Hybrid Retrieval (RRF)` · `Pinecone` · `LLM-as-Judge` · `Hallucination Detection` · `Groq`

**Rule: run the app, use the real numbers it prints. Never invent metrics.**

## The 60-second interview pitch

> "I built a competitive intelligence system where four specialist agents analyze a company in parallel roles — research, technology, market, and threats. Each agent generates its own search queries, retrieves evidence through hybrid search — Pinecone semantic vectors plus BM25 keyword matching, merged with Reciprocal Rank Fusion — then a Groq LLM re-ranks the candidates as a judge. Agents write their sections citing only retrieved evidence, a cross-check pass flags contradictions between them, and a synthesizer produces the executive brief. I measure quality with citation coverage and a number-fidelity metric that catches hallucinated figures — any number in the report that doesn't exist in the retrieved evidence gets flagged. The whole thing runs on free tiers: Groq for reasoning, Pinecone for vectors and hosted embeddings, so there's zero infrastructure and zero monthly cost."

## Deep-dive Q&A

**Why hybrid retrieval instead of pure vector search?**
> Semantic search misses exact terms — ticker symbols, product names, "$300M". BM25 catches exact matches but misses paraphrases. RRF merges the two rankings without needing score calibration, since it only uses ranks. In my testing, company-specific numeric queries are exactly where BM25 rescues vector search.

**Why Reciprocal Rank Fusion specifically?**
> Vector similarity scores and BM25 scores live on incomparable scales, so weighted score averaging is fragile. RRF sidesteps that: each result contributes 1/(k+rank), so it's scale-free, robust, and one line of code. It's what production search systems (e.g. hybrid search in major engines) actually use.

**Why LLM-as-judge re-ranking? Isn't that expensive?**
> One batched call per agent — the judge scores 16 candidates at once, so it's 4 extra LLM calls per report. Cross-encoder re-rankers would be cheaper per token but add a model dependency; on Groq's free tier the judge call costs nothing and lifts precision of the final evidence set noticeably. I'd swap to a dedicated re-ranker (Cohere, Voyage) at scale.

**How do agents "debate"?**
> Deliberately lightweight: after all four sections are written, a cross-check pass reads them together and flags contradictions — e.g., Research citing growth while Threat cites decline. I chose one synthesis-level pass over multi-round agent-to-agent messaging because it captures most of the value at a fraction of the calls. I can articulate the upgrade path: turn conflicts into re-query loops with a budget cap.

**How do you prevent hallucinations?**
> Three layers. Prompt: agents may only use numbered evidence and must cite [n] or say "no evidence found." Measurement: citation coverage and number fidelity computed on every report. Design: retrieval-first — the model never answers from parametric memory about the company; everything flows through the vector store.

**What breaks at scale, and what would you change?**
> Groq rate limits first — I'd add request queuing or move to paid tier. BM25 currently loads the chunk store in memory per process — fine for thousands of chunks, but I'd move to a search service past ~1M. Agents run sequentially to respect free-tier limits; with budget they're embarrassingly parallel (asyncio). And I'd add an eval harness with labeled relevance judgments to report precision@k properly instead of proxy metrics.

**Trap: "Is the sample data real?"**
> No — the bundled corpus is synthetic for a reliable demo; live mode ingests real NewsAPI/GitHub/arXiv data. Being upfront about this reads as integrity, and the architecture is identical either way.
