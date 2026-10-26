"""
CLI entrypoint: run the full multi-agent analysis and print/save the brief.

Usage:
    python -m src.report --company "OpenAI"
"""

import argparse
import json
import re

from src.agents import analyze_company, normalize_citations
from src.config import RESULTS_DIR, require

# A number with optional thousands separators and an optional scale word,
# so "$7 billion", "$7000M" and "7,000 million" all read as 7e9.
NUM_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\d.,]\d)"
    r"(?:\s*(k|K|thousand|M|mn|million|B|bn|billion|T|trillion)(?![A-Za-z]))?")
SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "M": 1e6, "mn": 1e6, "million": 1e6,
         "B": 1e9, "bn": 1e9, "billion": 1e9, "T": 1e12, "trillion": 1e12}
CITE_RE = re.compile(r"\[\d+\]")
ABSTAIN_RE = re.compile(r"no (?:evidence|information|data) (?:found|available)", re.I)


def numbers(text: str) -> list[tuple[float, float, int]]:
    """(mantissa, scale, decimals) for every number in text."""
    out = []
    for raw, unit in NUM_RE.findall(text):
        digits = raw.replace(",", "")
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        out.append((float(digits), SCALE.get(unit, 1.0), decimals))
    return out


def is_grounded(num: tuple[float, float, int], evidence_values: set[float]) -> bool:
    """A number is grounded if some evidence value, expressed in the same unit
    and rounded to the same precision, equals it ("2.9k" matches 2,934)."""
    mantissa, scale, decimals = num
    return any(round(v / scale, decimals) == mantissa for v in evidence_values)


def groundedness(report: dict) -> dict:
    """Two cheap hallucination checks on the final output:
    - citation coverage: % of factual bullets that carry a [n] citation
      (bullets that honestly say "no evidence found" are counted separately)
    - number fidelity: % of numbers in sections that appear in retrieved
      evidence, after normalizing units and thousands separators
    """
    bullets, cited, abstained, nums, grounded_nums = 0, 0, 0, 0, 0
    for s in report["sections"]:
        evidence_values = {m * sc for m, sc, _ in numbers(" ".join(s["evidence_texts"]))}
        for line in normalize_citations(s["section"]).splitlines():
            line = line.strip()
            if not line or len(line) < 15:
                continue
            if ABSTAIN_RE.search(line) and not CITE_RE.search(line):
                abstained += 1
                continue
            bullets += 1
            if CITE_RE.search(line):
                cited += 1
            for n in numbers(CITE_RE.sub("", line)):
                nums += 1
                if is_grounded(n, evidence_values):
                    grounded_nums += 1
    return {
        "citation_coverage": round(cited / bullets, 3) if bullets else 0.0,
        "number_fidelity": round(grounded_nums / nums, 3) if nums else 1.0,
        "bullets": bullets,
        "cited": cited,
        "abstentions": abstained,
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
