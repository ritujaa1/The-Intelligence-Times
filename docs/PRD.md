# PRD — The Intelligence Times

**Product:** An agentic RAG system that produces cited competitive-intelligence briefs on any company, typeset as a newspaper front page.

| | |
|---|---|
| **Status** | Shipped — v1.0 live at [theintelligencetimes.streamlit.app](https://theintelligencetimes.streamlit.app) |
| **Owner** | Kalpesh Borse |
| **Last updated** | 31 July 2026 |
| **Repo** | [github.com/imkalpx/agentic-rag-ci](https://github.com/imkalpx/agentic-rag-ci) |

---

## 1. Problem

Competitive research is a chore with a trust problem.

Someone evaluating a company — a founder sizing up a rival, an analyst preparing a note, a candidate researching an employer — spends hours reading news, GitHub activity, papers, and pricing pages, then assembles a mental picture that nobody else can audit. The work is slow, and the output is unverifiable.

General-purpose LLMs make this faster and *worse*. Ask one about a company's revenue and you get a confident figure with no source, no date, and no way to tell whether it was retrieved, remembered, or invented. For competitive intelligence specifically — a domain dense with numbers, where a wrong market-share figure propagates into a real decision — unattributed fluency is a defect, not a feature.

**The gap:** there is no lightweight tool that produces a structured competitive brief where *every claim points at the document it came from*, and where the system tells you how much of its own output it can vouch for.

## 2. Goals

**G1. Attribution by construction.** Every factual claim carries a source marker. The model may only use retrieved evidence, and must say "no evidence found" rather than fill the gap.

**G2. Self-reported trustworthiness.** The system measures and displays its own groundedness on every output. A reader should never have to take the brief on faith.

**G3. Breadth in one pass.** A single request yields four analytical perspectives — research, technology, market, threat — rather than one flat summary, plus an explicit note on where those perspectives contradict each other.

**G4. Zero cost, zero setup.** Runs entirely on free tiers with no local ML dependencies. Anyone can clone it and have it working in five minutes; the hosted version needs nothing at all.

**G5. Legible output.** The brief should be a pleasure to read and immediately shareable — not a wall of chat text.

### Non-goals

- **Not a real-time monitoring product.** No alerting, no scheduled re-crawls, no diffing over time. Briefs are generated on request.
- **Not investment advice**, and it says so on the page.
- **Not a general chatbot.** No follow-up conversation; the unit of output is a brief.
- **Not multi-tenant SaaS.** No accounts, no billing, no per-user isolation beyond company namespaces.
- **Not a comprehensive data platform.** Four free sources, not a licensed data pipeline.

## 3. Users

**Primary — the evaluator.** A founder, PM, analyst, or job candidate who needs a defensible picture of a company in minutes and cares that the numbers are checkable. Values: source links, an explicit statement of what the evidence doesn't cover, and something they can forward to a colleague.

**Secondary — the technical reviewer.** An engineer or hiring manager assessing the *system* rather than the company. Values: visible retrieval internals — re-rank scores, per-agent latency, the queries each agent generated, the groundedness metrics.

The second audience is why the UI exposes machinery that a pure consumer product would hide.

## 4. User stories

- As an evaluator, I type a company name and get a complete brief in under a minute, so I can skip an afternoon of reading.
- As an evaluator, I see a source next to every claim, so I can verify anything that matters before I act on it.
- As an evaluator, I see where the analysis contradicts itself, so I'm not handed false confidence.
- As an evaluator, I analyze a company nobody has researched yet, without touching a terminal.
- As an evaluator, I send someone a link that prints the brief on load.
- As a reviewer, I see which queries each agent wrote and how the retrieved evidence scored, so I can judge the retrieval quality myself.
- As a reviewer, I see the system's own hallucination metrics, so I can calibrate how much to trust it.
- As an operator, when something fails — rate limit, missing archive, bad key — I get a plain explanation of what to do, not a stack trace.

## 5. Requirements

### Must have (v1 — all shipped)

| ID | Requirement |
|---|---|
| R1 | Four specialist agents (research, technology, market, threat), each retrieving evidence scoped to its own domain |
| R2 | Each agent generates its own search queries rather than reusing the raw company name |
| R3 | Hybrid retrieval: semantic + keyword search, rank-fused; no score calibration required |
| R4 | Relevance re-ranking over fused candidates, with graceful fallback if it fails |
| R5 | Generation constrained to retrieved evidence, with mandatory citation markers and an explicit "no evidence found" escape |
| R6 | Cross-check pass surfacing contradictions between agents |
| R7 | Executive summary + strategic recommendation grounded in the sections |
| R8 | Citation coverage and number-fidelity metrics computed and displayed on every brief |
| R9 | Ingestion from live sources (news, code, research) with per-source graceful degradation |
| R10 | Per-company isolation so one company's evidence cannot leak into another's brief |
| R11 | Web app requiring no terminal for either ingestion or analysis |
| R12 | Newspaper-broadsheet presentation with sources, timings, and metrics visible |
| R13 | Shareable URLs that auto-print a brief |
| R14 | Standalone HTML export of a saved brief, renderable with no API calls |
| R15 | Human-readable failure states for every expected error (rate limit, unknown company, missing keys) |
| R16 | $0 running cost; no local ML dependencies |

### Should have (v1.1)

| ID | Requirement | Why |
|---|---|---|
| R17 | **Brief caching per company** | The binding constraint on the public demo: the free LLM tier allows 3–4 briefs/day. Serving a cached edition to repeat visitors removes the ceiling for the common case |
| R18 | **Back-issues archive** | Saved briefs and the renderer already exist; listing past editions makes the product feel alive and doubles as the cache's front door |
| R19 | **PDF download** | The export already produces print-ready HTML; this is the natural sharing format for a brief |

### Could have (later)

- Parallel agent execution (~25s → ~7s) once rate limits allow
- Conflict-driven re-query loops — turn the cross-check from a report into a control signal
- Company comparison view (two briefs side by side)
- Freshness indicators — how old is the evidence behind each claim
- A real evaluation harness: labeled relevance judgments, precision@k, claim-level entailment

### Explicitly rejected

- **Chat follow-ups.** Would reintroduce ungrounded answers through the back door and undermine G1.
- **Auto-refresh / scheduled crawls.** Multiplies API cost against a free-tier budget for a product whose unit of value is a one-off brief.
- **Hiding the machinery behind a clean consumer UI.** The visible internals serve the secondary audience and cost the primary one very little.

## 6. Success metrics

| Metric | Target | Actual (v1) |
|---|---|---|
| Citation coverage | > 70% | **79%** |
| Number fidelity | > 70% | **76–80%** |
| Time to brief | < 60s | **~25s** (24.8 / 25.8 / 26.4s measured) |
| Sources cited per brief | > 15 | **21–24** |
| Infrastructure cost | $0/month | **$0/month** |
| Setup to first brief | < 5 min | **~3 min** (or zero, hosted) |
| Live ingestion works end to end | Yes | **Yes** — 54 documents → 56 chunks |

**Counter-metric:** number fidelity must not be improved by weakening the check. The metric exists to detect degradation, so it stays deliberately untuned.

## 7. Design decisions & tradeoffs

**Hybrid retrieval over pure vector search.** Semantic search is weak exactly where this domain is dense: exact figures, product names, version numbers. Keyword search covers that blind spot. Cost: a second index to maintain, held locally.

**Rank fusion over weighted score blending.** Similarity scores and keyword scores are not on comparable scales, and any weighting needs recalibration as the corpus shifts. Fusing on rank alone is scale-free and needs no tuning.

**LLM-as-judge re-ranking over a dedicated re-ranker.** Free on the current tier and adds no dependency. Would swap to a cross-encoder at scale for cost and latency.

**One cross-check pass over multi-round agent debate.** Captures the contradictions that matter at a fraction of the calls. Upgrade path stated rather than built.

**Hosted embeddings over a local model.** Removes PyTorch and model downloads entirely — the repo is ~5MB and deploys anywhere. Cost: a network hop and embedding-model lock-in.

**Sequential agents.** Respects free-tier rate limits at the cost of ~18 seconds that parallelism would recover.

**Newspaper metaphor.** Cited sources, an editorial line, correspondents who disagree, a corrections notice — the form matches what the system actually produces, and attribution-dense layout is a problem newspapers solved a century ago. It also forced the typesetting layer to be independent of the web framework, which is what enables export.

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Free LLM tier daily cap** (100K tokens ≈ 3–4 briefs/day) | Public demo stops mid-day | Readable rate-limit notice today; caching (R17) is the real fix |
| Model deprecation on the provider | Total outage | Model name is a config value, swappable via env var |
| Upstream source outage or schema change | Thinner corpus | Every fetcher degrades independently; a dead source is skipped, not fatal |
| Sparse evidence for obscure companies | Weak or empty brief | Category filter falls back to unfiltered retrieval; agents write "no evidence found" rather than inventing |
| Reader over-trusts the output | Bad decision | Metrics displayed on every brief; synthetic sample corpus disclosed; explicit "not investment advice" |
| Source name ≠ GitHub org name | Missing technology evidence | Known limitation; documented |

## 9. Open questions

1. Should cached briefs be dated and re-runnable ("re-print this edition"), or immutable back issues? Leaning immutable, with a fresh run creating a new edition.
2. Is number fidelity worth splitting into "verbatim" vs "derived" to separate genuine hallucination from arithmetic? More honest, but a more complex number to explain.
3. Does the newspaper framing scale to a comparison view, or does the metaphor break when two companies share a page?

## 10. Appendix — v1 scope as shipped

Four agents · hybrid retrieval (semantic + BM25 + RRF) · LLM-as-judge re-ranking · grounded citation-constrained generation · conflict cross-check · executive synthesis · groundedness metrics · live ingestion from NewsAPI + GitHub + arXiv · per-company namespaces · newspaper web app with in-app ingestion · shareable auto-print URLs · standalone HTML export · deployed publicly at $0/month.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how each piece works.
