"""
Agent layer: 4 specialist agents + a synthesizer.

Each agent:
  1. Generates 3 targeted search queries for its specialty (Groq)
  2. Hybrid-retrieves grounded evidence from Pinecone + BM25 (its category first,
     falling back to all categories if its namespace slice is thin)
  3. Writes its report section citing evidence as [1], [2], ... (Groq)

Then the synthesizer cross-checks the four sections for conflicts (one extra
LLM pass = lightweight "agent debate") and writes the executive summary.
"""

import re
import time

from src.ingest import slugify
from src.retrieval import hybrid_retrieve
from src.vectors import llm, llm_json

AGENTS = {
    "Research Agent": {
        "category": "news",
        "focus": "recent news, funding, partnerships, product launches, hiring signals",
    },
    "Technology Agent": {
        "category": "tech",
        "focus": "technology stack, open-source activity, research output, engineering strengths",
    },
    "Market Agent": {
        "category": "market",
        "focus": "pricing, customer segments, market share, go-to-market, competitive positioning",
    },
    "Threat Agent": {
        "category": "threat",
        "focus": "weaknesses, risks, emerging competitors, regulatory exposure",
    },
}

# gpt-oss was trained to cite as 【1】 or 【1†L3】; normalize to the [1] the
# renderer and groundedness metrics expect.
NATIVE_CITE_RE = re.compile(r"【(\d+)[^】]*】")


def normalize_citations(text: str) -> str:
    return NATIVE_CITE_RE.sub(r"[\1]", text)


GROUNDING_RULES = (
    "Use ONLY the numbered evidence passages provided. Cite every factual claim "
    "with [n] markers. If the evidence does not cover something, write "
    "'No evidence found' for that point instead of guessing. Never invent numbers."
)


def run_agent(name: str, spec: dict, company: str) -> dict:
    t0 = time.time()
    namespace = slugify(company)

    # 1. Query generation
    queries = llm_json(
        f'You are the {name} analyzing the company "{company}". '
        f"Your focus: {spec['focus']}. Generate 3 short, diverse search queries "
        f'to find evidence. Return JSON: {{"queries": ["...", "...", "..."]}}',
        temperature=0.4, max_tokens=200,
    ).get("queries", [f"{company} {spec['focus']}"])[:3]

    # 2. Retrieval (category-scoped, fallback to all categories)
    evidence, stats = hybrid_retrieve(queries, namespace, category=spec["category"])
    if len(evidence) < 3:
        evidence, stats = hybrid_retrieve(queries, namespace, category=None)

    # 3. Grounded section writing
    numbered = "\n\n".join(
        f"[{i+1}] ({e['title']} — {e['source']}) {e['text']}"
        for i, e in enumerate(evidence))
    section = llm(
        f'Write the "{name}" section of a competitive intelligence brief on '
        f'"{company}". Focus: {spec["focus"]}.\n\nEVIDENCE:\n{numbered}\n\n'
        f"{GROUNDING_RULES}\nFormat: 4-7 tight bullet points.",
        temperature=0.2, max_tokens=500,
    )
    return {
        "agent": name,
        "queries": queries,
        "section": normalize_citations(section),
        "sources": [{"n": i + 1, "title": e["title"], "source": e["source"],
                     "rerank_score": e.get("rerank_score")}
                    for i, e in enumerate(evidence)],
        "evidence_texts": [e["text"] for e in evidence],
        "stats": {**stats, "total_ms": round((time.time() - t0) * 1000)},
    }


def cross_check(sections: list[dict], company: str) -> str:
    """Lightweight agent debate: one pass to surface contradictions."""
    joined = "\n\n".join(f"### {s['agent']}\n{s['section']}" for s in sections)
    return llm(
        f"Four analyst agents wrote these sections about {company}:\n\n{joined}\n\n"
        "Identify any contradictions or tensions between the sections "
        "(e.g., one cites growth while another cites decline). "
        "If none, say 'No conflicts detected.' Max 3 bullet points.",
        temperature=0.1, max_tokens=250,
    )


def synthesize(sections: list[dict], conflicts: str, company: str) -> str:
    joined = "\n\n".join(f"### {s['agent']}\n{s['section']}" for s in sections)
    return llm(
        f"Competitive intelligence sections on {company}:\n\n{joined}\n\n"
        f"Cross-check notes: {conflicts}\n\n"
        "Write an EXECUTIVE SUMMARY (3-4 sentences) and a STRATEGIC "
        "RECOMMENDATION (2-3 sentences) for a company competing with them. "
        "Ground everything in the sections above; do not add new facts.",
        temperature=0.3, max_tokens=350,
    )


def analyze_company(company: str, progress=print) -> dict:
    t0 = time.time()
    sections = []
    for name, spec in AGENTS.items():
        progress(f"→ {name} working...")
        sections.append(run_agent(name, spec, company))
    progress("→ Cross-checking for conflicts...")
    conflicts = cross_check(sections, company)
    progress("→ Synthesizing final brief...")
    summary = synthesize(sections, conflicts, company)
    return {
        "company": company,
        "sections": sections,
        "conflicts": conflicts,
        "executive_summary": summary,
        "total_seconds": round(time.time() - t0, 1),
    }
