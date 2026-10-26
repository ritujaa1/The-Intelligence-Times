"""
The Intelligence Times — newspaper-style front end for the agentic RAG
competitive-intelligence pipeline (Economic Times-inspired salmon newsprint).

Typesetting lives in app/newsprint.py so saved briefs can be rendered without
Streamlit (see src/export_html.py).

Run:
    streamlit run app/streamlit_app.py
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.newsprint import (STYLE, back_matter, desk_grid, esc, lead_story,
                           masthead, md_block_to_html)
from src.agents import analyze_company
from src.config import CHUNK_STORE, GROQ_API_KEY, PINECONE_API_KEY
from src.ingest import ingest, slugify
from src.report import groundedness

st.set_page_config(page_title="The Intelligence Times", page_icon="🗞️",
                   layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)


def known_companies() -> list[str]:
    if not CHUNK_STORE.exists():
        return []
    return sorted(json.loads(CHUNK_STORE.read_text()).keys())


def notice(kicker: str, body: str) -> None:
    st.markdown(f"<div class='correction'><div class='kicker'>{kicker}</div>{body}</div>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Masthead
# ---------------------------------------------------------------------------

st.markdown(masthead(date.today().strftime("%A, %B %d, %Y").upper()),
            unsafe_allow_html=True)

if not (GROQ_API_KEY and PINECONE_API_KEY):
    notice("NOTICE TO READERS",
           "The presses are stopped: set <b>GROQ_API_KEY</b> and "
           "<b>PINECONE_API_KEY</b> in <code>.env</code> (locally) or in "
           "Streamlit <i>Secrets</i> (cloud), then reload.")
    st.stop()

# ---------------------------------------------------------------------------
# Commissioning desk
# ---------------------------------------------------------------------------

st.markdown("<div class='deskline'>COMMISSION TODAY'S BRIEF</div>", unsafe_allow_html=True)
col1, col2 = st.columns([3, 1])
with col1:
    company = st.text_input("Company", label_visibility="collapsed",
                            placeholder="Name a company — e.g. OpenAI, Anthropic, Mistral AI")
with col2:
    run = st.button("Print the brief", use_container_width=True)

fresh = st.checkbox("Wire in fresh documents first (Google News · GitHub · arXiv) — "
                    "required for companies not yet in the archives")
archives = known_companies()
if archives:
    st.markdown(f"<div class='archives'>In today's archives: {' · '.join(archives)}</div>",
                unsafe_allow_html=True)

# Shareable editions: /?company=OpenAI auto-prints the brief on first load.
auto_company = st.query_params.get("company", "")
if auto_company and not st.session_state.get("_auto_ran"):
    st.session_state["_auto_ran"] = True
    company, run = auto_company, True

# ---------------------------------------------------------------------------
# Run the presses
# ---------------------------------------------------------------------------

if run and company.strip():
    company = company.strip()

    if slugify(company) not in known_companies() and not fresh:
        notice("CORRECTIONS &amp; CLARIFICATIONS",
               f"No file on <b>{esc(company)}</b> in the archives. Tick "
               f"<i>“Wire in fresh documents”</i> above and print again, or ingest "
               f"from the terminal: <code>python -m src.ingest --company "
               f"\"{esc(company)}\"</code>")
        st.stop()

    status = st.status("The newsroom is at work...", expanded=True)
    try:
        if fresh:
            status.write("→ Wire desk: fetching fresh documents (Google News · GitHub · arXiv)...")
            ingest(company)
        report = analyze_company(company, progress=status.write)
    except Exception as e:
        status.update(label="Presses stopped", state="error")
        notice("CORRECTIONS &amp; CLARIFICATIONS", esc(str(e)))
        st.stop()

    report["groundedness"] = groundedness(report)
    status.update(label=f"Edition printed in {report['total_seconds']}s", state="complete")

    st.markdown(lead_story(report), unsafe_allow_html=True)
    st.markdown(desk_grid(report), unsafe_allow_html=True)
    st.markdown(back_matter(report), unsafe_allow_html=True)
