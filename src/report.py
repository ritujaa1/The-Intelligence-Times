"""
CLI entrypoint: run the full multi-agent analysis and print/save the brief.

Usage:
    python -m src.report --company "OpenAI"
"""

import argparse
import json
import re

from src.agents import analyze_company
from src.config import RESULTS_DIR, require

NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def groundedness(report: dict) -> dict:
    """Two cheap hallucination checks on the final output:
    - citation coverage: % of section bullets that carry a [n] citation
    - number fidelity: % of numbers in sections that appear in retrieved evidence
    """
    bullets, cited, nums, grounded_nums = 0, 0, 0, 0
    for s in report["sections"]:
        evidence_text = " ".join(s["evidence_texts"])
        evidence_nums = set(NUM_RE.findall(evidence_text))
        for line in s["section"].splitlines():
            line = line.strip()
            if not line or len(line) < 15:
                continue
            bullets += 1
            if re.search(r"\[\d+\]", line):
                cited += 1
            for n in NUM_RE.findall(re.sub(r"\[\d+\]", "", line)):
                nums += 1
                if n in evidence_nums:
                    grounded_nums += 1
    return {
        "citation_coverage": round(cited / bullets, 3) if bullets else 0.0,
        "number_fidelity": round(grounded_nums / nums, 3) if nums else 1.0,
        "bullets": bullets,
        "cited": cited,
        "numbers": nums,
        "grounded_numbers": grounded_nums,
    }


def render(report: dict) -> str:
    lines = [f"{'='*64}", f"COMPETITIVE INTELLIGENCE BRIEF: {report['company']}",
             f"{'='*64}", "", "EXECUTIVE SUMMARY & RECOMMENDATION",
             report["executive_summary"], ""]
    for s in report["sections"]:
        lines += [f"--- {s['agent'].upper()} " + "-" * (40 - len(s["agent"])),
                  s["section"], "", "Sources:"]
        lines += [f"  [{src['n']}] {src['title']} — {src['source']}"
                  for src in s["sources"]]
        lines += [f"  (retrieval {s['stats']['retrieval_ms']}ms, "
                  f"re-rank {s['stats']['rerank_ms']}ms)", ""]
    lines += ["--- CONFLICT CHECK " + "-" * 30, report["conflicts"], ""]
    g = report["groundedness"]
    lines += ["--- QUALITY METRICS " + "-" * 29,
              f"Citation coverage: {g['citation_coverage']:.0%}   "
              f"Number fidelity: {g['number_fidelity']:.0%}   "
              f"Total time: {report['total_seconds']}s"]
    return "\n".join(lines)


def main():
    require("GROQ_API_KEY", "PINECONE_API_KEY")
    p = argparse.ArgumentParser()
    p.add_argument("--company", required=True)
    args = p.parse_args()

    report = analyze_company(args.company)
    report["groundedness"] = groundedness(report)

    out = RESULTS_DIR / f"brief_{args.company.lower().replace(' ', '_')}.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n" + render(report))
    print(f"\n✓ Saved -> {out}")


if __name__ == "__main__":
    main()
