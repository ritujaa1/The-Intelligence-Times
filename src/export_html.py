"""
Render a saved brief (results/brief_<company>.json) as a standalone newspaper
page — no API calls, no Streamlit. Useful for sharing an edition, archiving a
back issue, or printing to PDF from the browser.

Usage:
    python -m src.export_html --company "OpenAI"
    python -m src.export_html --company "OpenAI" --out docs/img/brief.html
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "app"))

import newsprint  # noqa: E402

from src.config import RESULTS_DIR  # noqa: E402


def export(company: str, out: Path | None = None) -> Path:
    slug = company.lower().replace(" ", "_")
    src = RESULTS_DIR / f"brief_{slug}.json"
    if not src.exists():
        raise SystemExit(f"No saved brief at {src}. Run: python -m src.report "
                         f'--company "{company}"')
    report = json.loads(src.read_text())
    page = newsprint.standalone_page(report,
                                     date.today().strftime("%A, %B %d, %Y").upper())
    out = out or RESULTS_DIR / f"brief_{slug}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--company", required=True)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    print(f"✓ Wrote {export(args.company, args.out)}")
