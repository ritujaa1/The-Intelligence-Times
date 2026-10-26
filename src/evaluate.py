"""
Batch evaluation: run full briefs across several companies and aggregate the
groundedness metrics from src/report.py.

Two corpora are covered:
  - sample: the bundled synthetic archives (OpenAI, Anthropic, Mistral AI),
    each run --repeats times to show run-to-run variance
  - live:   companies freshly ingested from Google News + GitHub + arXiv

Scoring (per brief, see report.groundedness):
  - citation coverage = bullets carrying a [n] citation / all bullets
  - number fidelity   = numbers that appear in that agent's retrieved
                        evidence / all numbers written (hallucination proxy)
Aggregates are pooled over every bullet / number, so long briefs weigh more.

Usage:
    python -m src.evaluate
    python -m src.evaluate --live Nvidia Tesla --repeats 1
"""

import argparse
import json
import statistics
import time

from src.agents import analyze_company
from src.config import RESULTS_DIR, require
from src.ingest import ingest
from src.report import groundedness

SAMPLE = ["OpenAI", "Anthropic", "Mistral AI"]
LIVE = ["Nvidia", "Tesla", "Stripe", "Databricks", "Microsoft"]


def run_one(company: str, corpus: str) -> dict | None:
    try:
        report = analyze_company(company, progress=lambda *a, **k: None)
    except Exception as e:  # e.g. Groq free tier's 200k tokens/day limit
        print(f"  {company:<12} {corpus:<6} FAILED: {str(e)[:120]}", flush=True)
        return None
    g = groundedness(report)
    row = {"company": company, "corpus": corpus,
           "seconds": report["total_seconds"], **g}
    print(f"  {company:<12} {corpus:<6} cite {g['citation_coverage']:.0%}  "
          f"numfid {g['number_fidelity']:.0%}  bullets {g['bullets']}  "
          f"numbers {g['numbers']}  {report['total_seconds']}s", flush=True)
    return row


def pooled(rows: list[dict]) -> dict:
    bullets = sum(r["bullets"] for r in rows)
    nums = sum(r["numbers"] for r in rows)
    return {
        "briefs": len(rows),
        "bullets": bullets,
        "numbers": nums,
        "citation_coverage": round(sum(r["cited"] for r in rows) / bullets, 3) if bullets else 0.0,
        "number_fidelity": round(sum(r["grounded_numbers"] for r in rows) / nums, 3) if nums else 1.0,
        "citation_coverage_range": [min(r["citation_coverage"] for r in rows),
                                    max(r["citation_coverage"] for r in rows)],
        "number_fidelity_range": [min(r["number_fidelity"] for r in rows),
                                  max(r["number_fidelity"] for r in rows)],
        "median_seconds": statistics.median(r["seconds"] for r in rows),
    }


def main():
    require("GROQ_API_KEY", "PINECONE_API_KEY")
    p = argparse.ArgumentParser()
    p.add_argument("--sample", nargs="*", default=SAMPLE)
    p.add_argument("--live", nargs="*", default=LIVE)
    p.add_argument("--repeats", type=int, default=2, help="runs per sample company")
    args = p.parse_args()

    rows = []
    print(f"Sample corpus ({len(args.sample)} companies x {args.repeats} runs)")
    for company in args.sample:
        for _ in range(args.repeats):
            rows.append(run_one(company, "sample"))
            save(rows)

    print(f"Live corpus ({len(args.live)} companies, freshly ingested)")
    for company in args.live:
        ingest(company)
        rows.append(run_one(company, "live"))
        save(rows)
        time.sleep(5)  # stay under Groq free-tier rate limits

    summary = save(rows)
    print(json.dumps({k: summary[k] for k in ("overall", "sample", "live")}, indent=2))
    print(f"\n✓ Saved -> {RESULTS_DIR / 'eval_summary.json'}")


def save(rows: list[dict | None]) -> dict:
    """Write the summary after every brief so a rate-limit stop loses nothing."""
    rows = [r for r in rows if r]
    by = lambda c: [r for r in rows if r["corpus"] == c]
    summary = {
        "date": time.strftime("%Y-%m-%d"),
        "overall": pooled(rows) if rows else None,
        "sample": pooled(by("sample")) if by("sample") else None,
        "live": pooled(by("live")) if by("live") else None,
        "runs": rows,
    }
    (RESULTS_DIR / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
