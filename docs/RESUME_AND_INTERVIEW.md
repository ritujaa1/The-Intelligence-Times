# Resume Bullets & Interview Guide

Companion to [ARCHITECTURE.md](ARCHITECTURE.md), which walks the system step by step.

**Live app:** https://theintelligencetimes.streamlit.app · **Repo:** https://github.com/imkalpx/agentic-rag-ci

All metrics below are **real, measured numbers** from actual runs. Re-run the app and update them if they change — never quote a number you haven't seen the system print.

---

## Resume

**Title line:**

> **The Intelligence Times — Agentic RAG Competitive Intelligence** | Python, Pinecone, Groq, Hybrid Retrieval, Multi-Agent LLM
> *Live: theintelligencetimes.streamlit.app · Code: github.com/imkalpx/agentic-rag-ci*

**Bullets:**

- Built a **multi-agent RAG system** in which four specialist agents (research, technology, market, threat) autonomously generate their own search queries, retrieve evidence from a **Pinecone** vector store via **hybrid search** (semantic + BM25 fused with Reciprocal Rank Fusion), and write fully source-attributed intelligence briefs — **~25s end to end**, 14 LLM calls per brief

- Implemented **LLM-as-judge re-ranking** (Groq Llama-3.3-70B scoring 16 candidates per agent in one batched call) plus an inter-agent conflict cross-check, achieving **79% citation coverage** and **80% number fidelity** — a custom hallucination metric that verifies every figure in the output exists in the retrieved evidence

- Engineered a **zero-local-ML ingestion pipeline** (NewsAPI, GitHub, arXiv) with 180-word overlapping chunking, **Pinecone-hosted embeddings** (multilingual-e5-large, 1024-dim) and per-company namespace isolation — ingesting **56 chunks from 54 live documents** in a single run at **$0/month** infrastructure cost

- **Deployed to production** on Streamlit Community Cloud with a custom newspaper-broadsheet UI, in-app live data ingestion, shareable auto-printing URLs, and a Streamlit-free typesetting module enabling standalone HTML/PDF export of any saved brief

**Skills line:** `Agentic RAG` · `Multi-Agent Orchestration` · `Hybrid Retrieval (BM25 + RRF)` · `Pinecone` · `LLM-as-Judge Re-ranking` · `Hallucination Detection` · `Groq` · `Streamlit`

**Shorter, two-bullet version** if space is tight:

- Built and deployed a multi-agent RAG system where 4 specialist LLM agents self-generate queries, retrieve via hybrid search (Pinecone semantic + BM25 + Reciprocal Rank Fusion), re-rank with an LLM-as-judge, and produce cited competitive-intelligence briefs in ~25s — measured at 79% citation coverage and 80% number fidelity on real runs
- Ran entirely on free tiers ($0/month, zero local ML dependencies) using Pinecone-hosted embeddings; shipped a live public web app with in-app ingestion from NewsAPI/GitHub/arXiv

---

## The 60-second pitch

> "I built a competitive intelligence system where four specialist agents analyze a company in parallel roles — research, technology, market, and threats. Each agent generates its own search queries, then retrieves evidence through hybrid search: Pinecone semantic vectors plus BM25 keyword matching, merged with Reciprocal Rank Fusion. A Groq LLM then re-ranks the fused candidates as a judge, and each agent writes its section citing only the numbered evidence it retrieved. A cross-check pass flags contradictions between agents, and a synthesizer produces the executive brief.
>
> The part I'm proudest of is the measurement. Every brief reports citation coverage and what I call number fidelity — I extract every number from the output and verify it appears in the retrieved evidence. Invented revenue figures fail that check by construction. Real runs land at 79% and 80%.
>
> The whole thing runs on free tiers with zero local ML — Pinecone hosts the embeddings, Groq does the reasoning — so it's about 5MB of Python, and it's deployed and public."

Then stop talking. Let them pick the thread.

---

## Deep-dive Q&A

**Why hybrid retrieval instead of pure vector search?**
> They fail in opposite directions. Semantic search is strong on paraphrase and weak on rare literals — exact figures like "$300M", product names like "GPT-5.6", ticker symbols. BM25 is the reverse. Competitive intelligence queries are full of exactly those literals, so BM25 rescues the vector search precisely where it's weakest. Using only one would have been a real quality loss on the numeric queries that matter most here.

**Why Reciprocal Rank Fusion specifically, over weighted score averaging?**
> Because cosine similarity and BM25 scores live on incomparable scales — cosine is bounded and bunched near the top, BM25 is unbounded and corpus-dependent. Any weighted average needs calibration that breaks the moment the corpus changes. RRF only reads *ranks*, never scores, so it's scale-free and needs no tuning. It's four lines of code, and it's what production hybrid search actually uses. The k=60 damping constant stops rank-1 from dominating so hard that agreement between retrievers stops counting — and consensus is the signal I actually want.

**Why LLM-as-judge re-ranking? Isn't that expensive?**
> One batched call per agent — the judge scores all 16 candidates at once, so it's 4 extra calls per brief, not 64. RRF optimizes recall; the judge adds precision on the final 6 passages that actually enter the prompt. Importantly it fails safe: if the judge call errors or returns malformed JSON, the code falls back to RRF ordering rather than dropping the brief. At scale I'd swap to a dedicated cross-encoder re-ranker like Cohere or Voyage — cheaper per token and lower latency — but on the free tier the judge costs nothing.

**What actually makes the four agents "specialists"? Isn't it just four prompts?**
> Two things, and I'd rather be precise about it than oversell. First, a category filter: chunks are tagged `news`/`tech`/`market`/`threat` at ingestion, and each agent's retrieval is scoped to its own slice, so the Market Agent never wades through GitHub repo descriptions. Second, a focus string that shapes both query generation and the writing brief. That's a cheap abstraction and it captures most of the value. What it is *not* is four fine-tuned models — and I think claiming otherwise would be dishonest about where the leverage actually comes from.

**How do the agents "debate"?**
> Deliberately lightweight. After all four sections are written, one pass reads them together and flags contradictions — Research citing 45% valuation growth while Threat cites 11% attrition and margin compression. I chose one synthesis-level pass over multi-round agent-to-agent messaging because it catches the contradictions that matter for a fraction of the calls. The upgrade path is clear if I needed it: turn each detected conflict into a targeted re-query loop with a budget cap so it can't spiral.

**How do you prevent hallucinations?**
> Three layers. **Prompt:** agents may only use the numbered evidence and must either cite `[n]` or write "no evidence found" — and that escape hatch does get used in real output, which is the model doing the right thing. **Design:** retrieval-first, so the model never answers from parametric memory about the company; everything flows through the vector store. **Measurement:** citation coverage and number fidelity on every brief, so I can see when it degrades rather than hoping.

**Tell me about number fidelity — and where does it fail?**
> I regex every number out of the generated prose, strip the citation markers so `[3]` isn't counted as 3, and check membership against the numbers in the retrieved evidence. A fabricated revenue figure fails by construction, because it doesn't exist in the source passages.
>
> Where it fails: it can't catch a *correct* number attached to a *wrong* claim, and it flags legitimately derived arithmetic as ungrounded. So it's a smoke detector, not a fire inspection. My real scores are 76–80%, and most of that gap is rephrased or derived figures rather than genuine hallucination. I deliberately didn't tune the metric to look better, because a metric I've gamed tells me nothing.

**What would a proper evaluation look like?**
> What I have are proxies. A real eval needs a labeled relevance set — annotated query/chunk pairs — so I could report precision@k and nDCG for the retrieval stage instead of inferring quality from downstream citations. For generation I'd want claim-level entailment checking against the evidence, either with an NLI model or a stronger judge model, and a held-out set of companies with human-verified briefs. That's the honest gap between "I measured something useful" and "I evaluated this."

**What breaks at scale?**
> Rate limits first, and I hit this for real: Groq's free tier is 100K tokens/day, a brief costs 25–30K, so it's 3–4 briefs a day before HTTP 429s. The app surfaces that as a readable notice instead of a stack trace, but the real fix is caching briefs per company so repeat visitors read the archive rather than re-running the presses.
>
> After that: BM25 loads the chunk store into process memory, which is fine for thousands of chunks and wrong past a million — that wants a real search service like OpenSearch. Agents run sequentially to respect rate limits, but they're embarrassingly parallel; with a paid tier and asyncio, total time drops to roughly the slowest agent, about 7 seconds instead of 25.

**Why Pinecone-hosted embeddings instead of running a model locally?**
> It removes PyTorch and a model download from the dependency tree entirely — the repo is about 5MB and installs in seconds on any machine, including a free Streamlit Cloud container with a small image budget. The tradeoff is a network hop per embedding call and vendor lock-in on the embedding model. For a project whose constraint was "$0 and must deploy anywhere," that was clearly right; for a latency-critical production system I'd reconsider.

**Walk me through a bug you hit in deployment.**
> The deployed app kept reporting no API keys even though the secrets were set. Two causes stacked. First, Streamlit Cloud only mirrors secrets into `os.environ` *after* `st.secrets` is first accessed, so my plain `os.getenv` found nothing — I changed config to check env vars first and fall back to `st.secrets`. Second, the secrets had been pasted as bare `KEY= value` instead of TOML `KEY = "value"`; invalid TOML makes the platform reject the entire file silently, so the app sees zero secrets and the symptom is identical to having set none. The lesson I took: an error message that says "keys missing" should distinguish "absent" from "unparseable," because those have completely different fixes.

**Why the newspaper UI? Isn't that decoration?**
> Partly it's craft — but the metaphor does real work. A brief with cited sources, an editorial line, correspondents who disagree with each other in a cross-examination box, and a corrections notice when something fails maps almost exactly onto what the system produces. Citations as red superscripts and sources in agate type are how newspapers have always handled attribution density, which is precisely my problem. And it forced a good architectural decision: I pulled the typesetting into a Streamlit-free module, which is what lets me render a saved brief to standalone HTML with no API calls — that's the export and PDF path.

**Trap: "Is the sample data real?"**
> No — the bundled corpus is synthetic, invented numbers, so the offline demo is instant and deterministic. Live mode ingests real NewsAPI, GitHub, and arXiv data, and I've run it end to end: 54 live documents, 56 chunks. The architecture is identical either way. I'd rather flag that upfront than have someone discover a made-up revenue figure and wonder what else I wasn't saying.

---

## Things worth volunteering

Interviewers respond well to engineers who name their own tradeoffs first:

- **The metric is a proxy and I know its failure modes** (derived numbers, right-number-wrong-claim).
- **The agents are a cheap abstraction** — category filter plus focus string, not fine-tuned specialists.
- **The debate is one pass, not multi-round** — a deliberate cost decision with a stated upgrade path.
- **The sample corpus is synthetic** — say it before you're asked.
- **Free tier is the binding constraint**, and caching is the fix I'd ship next.

## If you get 5 more minutes: what I'd build next

1. **Brief caching per company** — directly removes the rate-limit ceiling on a public demo.
2. **Back-issues archive** — the saved briefs and the HTML renderer already exist; listing them is small.
3. **Parallel agents** with asyncio — 25s → ~7s once rate limits allow.
4. **A real eval harness** — labeled relevance judgments, precision@k, claim-level entailment.
5. **Conflict-driven re-query loops** — turn the cross-check from a report into a control signal.
