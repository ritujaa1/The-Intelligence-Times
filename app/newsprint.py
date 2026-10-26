"""
Presentation layer for The Intelligence Times: the newsprint stylesheet and the
pure functions that typeset a brief as newspaper HTML.

Kept free of Streamlit imports so a saved brief can be rendered to a standalone
page (see src/export_html.py) without a running app or any API calls.
"""

import html as html_lib
import re
from urllib.parse import urlparse

STYLE = """<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;0,900;1,500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;600;700&display=swap');

:root {
  --ink: #1D1D1B;
  --red: #C2201F;
  --paper: #F6EBDC;
  --rule: rgba(29,29,27,.25);
}
.stApp { background: var(--paper); }
header[data-testid="stHeader"] { display: none; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1150px; padding-top: 1.3rem; padding-bottom: 3rem; }
.stApp p, .stApp li, .stApp label, .stApp span { color: var(--ink); }

/* masthead */
.topbar { display: flex; justify-content: space-between; gap: 1rem;
  border-top: 2px solid var(--ink); border-bottom: 1px solid var(--ink);
  padding: .3rem .1rem; font: 600 .7rem/1 'Inter', sans-serif; letter-spacing: .14em; }
.masthead { font: 900 4.2rem/1.02 'Playfair Display', serif; text-align: center;
  margin: .8rem 0 .45rem; color: var(--ink); }
.masthead .red { color: var(--red); }
.tagline { text-align: center; font: 600 .72rem/1.5 'Inter', sans-serif;
  letter-spacing: .26em; border-top: 1px solid var(--ink);
  border-bottom: 2px solid var(--ink); padding: .36rem 0; margin-bottom: 1.2rem; }

/* commissioning desk (input row) */
.deskline { font: 700 .68rem/1 'Inter', sans-serif; letter-spacing: .22em;
  color: var(--red); margin: .2rem 0 .35rem; }
.archives { font: italic 400 .85rem/1.5 'Source Serif 4', serif; opacity: .75;
  margin-top: .1rem; }
.stTextInput input { background: transparent; border: none;
  font: 500 1.05rem 'Source Serif 4', serif; color: var(--ink);
  padding: .55rem .8rem; }
div[data-baseweb="input"] { background: transparent; border: 1.5px solid var(--ink);
  border-radius: 0; }
div[data-baseweb="input"]:focus-within { border-color: var(--red); box-shadow: none; }
.stButton > button { background: var(--ink); border: none;
  border-radius: 0; letter-spacing: .18em;
  text-transform: uppercase; padding: .78rem 1.2rem; width: 100%; }
.stButton > button p { color: var(--paper) !important;
  font: 700 .8rem 'Inter', sans-serif; letter-spacing: .18em; }
.stButton > button:hover { background: var(--red); }
.stCheckbox { font-family: 'Inter', sans-serif; }
[data-testid="stExpander"], [data-testid="stStatus"] {
  border: 1px solid var(--ink); border-radius: 0; background: transparent; }

/* lead story */
.edition-rule { border-top: 3px solid var(--ink); margin-top: 1.4rem; }
.kicker { font: 700 .68rem/1 'Inter', sans-serif; letter-spacing: .22em;
  color: var(--red); margin: .55rem 0 .3rem; }
.headline { font: 900 3rem/1.05 'Playfair Display', serif; margin: .1rem 0 .5rem; }
.deck { font: italic 500 1.15rem/1.5 'Playfair Display', serif; margin: 0 0 .5rem; }
.byline { font: 600 .68rem/1.6 'Inter', sans-serif; letter-spacing: .12em;
  border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink);
  padding: .3rem 0; margin: .6rem 0 .9rem; }
.lead-story { column-count: 2; column-gap: 2.2rem;
  column-rule: 1px solid var(--rule); font: 400 1.02rem/1.65 'Source Serif 4', serif;
  text-align: justify; }
.lead-story p { margin: 0 0 .8rem; }
.lead-story p:first-of-type::first-letter { font: 900 3.4rem/0.85 'Playfair Display', serif;
  float: left; padding: .35rem .5rem 0 0; color: var(--red); }

/* editorial (recommendation) box */
.editorial { border: 2px solid var(--ink); padding: .9rem 1.1rem .7rem;
  margin: 1rem 0 0; background: rgba(29,29,27,.04); }
.editorial .kicker { margin-top: 0; }
.editorial p { font: italic 400 1rem/1.6 'Source Serif 4', serif; margin: 0 0 .5rem; }

/* desk grid */
.desk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 2.2rem;
  margin-top: 1.5rem; }
.desk { border-top: 3px solid var(--ink); padding: .1rem .2rem 1.1rem 0; }
.desk:nth-child(even) { border-left: 1px solid var(--rule); padding-left: 2.2rem; }
.desk h3 { font: 700 1.5rem/1.15 'Playfair Display', serif; margin: .15rem 0 .5rem; }
.desk ul { margin: 0 0 .6rem 1.1rem; padding: 0; }
.desk li { font: 400 .95rem/1.55 'Source Serif 4', serif; margin-bottom: .45rem;
  text-align: justify; }
.desk .sec-intro { font: italic 400 .9rem/1.5 'Source Serif 4', serif;
  margin: 0 0 .4rem; opacity: .8; }
.cite { color: var(--red); font: 700 .72em 'Inter', sans-serif; }
.agate { font: 400 .72rem/1.6 'Inter', sans-serif; opacity: .8;
  border-top: 1px dotted var(--ink); padding-top: .4rem; }
.agate b { font-weight: 700; }
.timing { font: italic 400 .72rem/1.4 'Source Serif 4', serif; opacity: .6;
  margin-top: .25rem; }

/* cross-examination */
.crossexam { border-top: 3px double var(--red); border-bottom: 3px double var(--red);
  margin-top: 1.6rem; padding: .6rem .2rem .8rem; }
.crossexam p, .crossexam li { font: 400 .98rem/1.6 'Source Serif 4', serif; }
.crossexam ul { margin: .2rem 0 0 1.1rem; }

/* metrics ticker */
.ticker { background: var(--ink); color: var(--paper); margin-top: 1.6rem;
  padding: .55rem .9rem; font: 600 .74rem/1 'Inter', sans-serif;
  letter-spacing: .14em; display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; }
.ticker span { color: var(--paper); }
.ticker b { color: #F2B8B5; font-weight: 700; }

.colophon { text-align: center; font: italic 400 .8rem/1.6 'Source Serif 4', serif;
  border-top: 1px solid var(--ink); margin-top: 1.4rem; padding-top: .5rem;
  opacity: .75; }

/* font overrides — Streamlit's theme CSS outranks single-class selectors */
.masthead, .headline, .desk h3, .deck,
.lead-story p:first-of-type::first-letter {
  font-family: 'Playfair Display', Georgia, serif !important; }
.lead-story, .lead-story p, .desk li, .desk .sec-intro, .archives, .deck,
.editorial p, .crossexam p, .crossexam li, .timing, .colophon, .correction,
.stTextInput input {
  font-family: 'Source Serif 4', Georgia, serif !important; }
.deck, .lead-story .sec-intro { font-style: italic; }
.topbar, .tagline, .kicker, .deskline, .agate, .ticker, .cite,
.stButton > button p {
  font-family: 'Inter', 'Helvetica Neue', sans-serif !important; }

/* corrections box (errors) */
.correction { border: 2px solid var(--red); padding: .8rem 1rem;
  font: 400 .95rem/1.6 'Source Serif 4', serif; margin-top: 1rem; }
.correction .kicker { margin-top: 0; }
</style>"""

DESKS = {
    "Research Agent": ("RESEARCH DESK", "Funding, partnerships & the news wire"),
    "Technology Agent": ("TECHNOLOGY DESK", "Stack, shipping cadence & research output"),
    "Market Agent": ("MARKET DESK", "Pricing, share & go-to-market"),
    "Threat Agent": ("THREAT DESK", "Risks, rivals & regulation"),
}


def esc(text: str) -> str:
    return html_lib.escape(text, quote=False)


def inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\[(\d+)\]", r"<sup class='cite'>[\1]</sup>", text)


def md_block_to_html(text: str) -> str:
    """Tiny markdown-ish converter for agent sections (bullets + bold + cites)."""
    out, in_list = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^[\*\-\u2022]\s+(.*)", line)
        content = inline_md(esc(m.group(1) if m else line))
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{content}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p class='sec-intro'>{content}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def split_summary(text: str) -> tuple[str, str]:
    t = re.sub(r"^\**\s*EXECUTIVE SUMMARY:?\**\s*", "", text.strip(), flags=re.I)
    parts = re.split(r"\**\s*STRATEGIC RECOMMENDATION:?\**\s*", t, flags=re.I)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def short_source(source: str) -> str:
    if source.startswith("http"):
        return urlparse(source).netloc.removeprefix("www.") or source
    return source


def masthead(dateline: str) -> str:
    return f"""
<div class="topbar"><span>VOL. I \u00b7 NO. 1</span><span>{dateline}</span>
<span>\u20b90.00 \u00b7 FREE-TIER EDITION</span></div>
<h1 class="masthead">The Intelligence <span class="red">Times</span></h1>
<div class="tagline">FOUR AI CORRESPONDENTS \u00b7 HYBRID RETRIEVAL \u00b7 EVERY CLAIM CITED AT THE PRESS</div>
"""


def lead_story(report: dict) -> str:
    company = report["company"]
    summary, recommendation = split_summary(report["executive_summary"])
    deck = esc(summary.split(". ")[0].rstrip(".") + ".") if summary else ""
    paras = "".join(f"<p>{inline_md(esc(p.strip()))}</p>"
                    for p in summary.split("\n") if p.strip())

    editorial = ""
    if recommendation:
        rec = "".join(f"<p>{inline_md(esc(p.strip()))}</p>"
                      for p in recommendation.split("\n") if p.strip())
        editorial = (f"<div class='editorial'><div class='kicker'>THE EDITORIAL LINE "
                     f"\u00b7 STRATEGIC RECOMMENDATION</div>{rec}</div>")

    return f"""
<div class="edition-rule"></div>
<div class="kicker">FRONT PAGE \u00b7 COMPETITIVE INTELLIGENCE BRIEF</div>
<div class="headline">The {esc(company)} File</div>
<div class="deck">{deck}</div>
<div class="byline">BY OUR RESEARCH, TECHNOLOGY, MARKET &amp; THREAT CORRESPONDENTS \u00b7
GROQ GPT-OSS-120B \u00b7 PINECONE HYBRID RETRIEVAL (SEMANTIC + BM25 + RRF)</div>
<div class="lead-story">{paras}</div>
{editorial}
"""


def desk_grid(report: dict) -> str:
    out = ["<div class='desk-grid'>"]
    for section in report["sections"]:
        kicker, subhead = DESKS.get(section["agent"], (section["agent"].upper(), ""))
        sources = " &nbsp;\u00b7&nbsp; ".join(
            f"<b>[{s['n']}]</b> {esc(s['title'][:70])} \u2014 {esc(short_source(s['source']))}"
            + (f" ({s['rerank_score']:.0f}/100)" if s.get("rerank_score") else "")
            for s in section["sources"])
        stats = section["stats"]
        out.append(f"""
<div class="desk">
  <div class="kicker">{kicker}</div>
  <h3>{esc(subhead)}</h3>
  {md_block_to_html(section["section"])}
  <div class="agate"><b>SOURCES:</b> {sources}</div>
  <div class="timing">Filed in {stats['total_ms']/1000:.1f}s \u2014 retrieval
  {stats['retrieval_ms']}ms \u00b7 re-rank {stats['rerank_ms']}ms \u00b7
  wires searched: {' / '.join(esc(q) for q in section['queries'])}</div>
</div>""")
    out.append("</div>")
    return "".join(out)


def back_matter(report: dict) -> str:
    g = report["groundedness"]
    total_sources = sum(len(s["sources"]) for s in report["sections"])
    return f"""
<div class="crossexam">
  <div class="kicker">CROSS-EXAMINATION \u00b7 WHERE OUR CORRESPONDENTS DISAGREE</div>
  {md_block_to_html(report["conflicts"])}
</div>
<div class="ticker">
  <span>CITATION COVERAGE <b>{g['citation_coverage']:.0%}</b></span>
  <span>NUMBER FIDELITY <b>{g['number_fidelity']:.0%}</b></span>
  <span>SOURCES CITED <b>{total_sources}</b></span>
  <span>BULLETS FILED <b>{g['bullets']}</b></span>
  <span>PRESS TIME <b>{report['total_seconds']}s</b></span>
</div>
<div class="colophon">Printed by four autonomous correspondents on the Groq\u2013Pinecone press.
Number fidelity is our hallucination check: figures absent from the retrieved evidence are
refused at the press. Not investment advice.</div>
"""


def standalone_page(report: dict, dateline: str) -> str:
    """Full self-contained HTML document for a saved brief."""
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>The Intelligence Times \u2014 {esc(report['company'])}</title>"
            f"{STYLE}<style>body{{background:#F6EBDC;margin:0;}}"
            f".sheet{{max-width:1150px;margin:0 auto;padding:1.3rem 1rem 3rem;}}</style>"
            f"</head><body><div class='sheet'>{masthead(dateline)}"
            f"{lead_story(report)}{desk_grid(report)}{back_matter(report)}"
            f"</div></body></html>")
