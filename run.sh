#!/bin/bash
# One-command runner. Usage: bash run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "Created .env — open it and paste your GROQ_API_KEY and PINECONE_API_KEY,"
  echo "then run  bash run.sh  again."
  exit 0
fi

echo ""
echo "1) Ingest a company (offline sample: OpenAI / Anthropic / Mistral AI)"
echo "2) Ingest a company (live: NewsAPI + GitHub + arXiv)"
echo "3) Generate intelligence brief (CLI)"
echo "4) Launch web app"
read -p "Choose [1-4]: " choice
case $choice in
  1) read -p "Company: " c; python -m src.ingest --company "$c" --offline ;;
  2) read -p "Company: " c; python -m src.ingest --company "$c" ;;
  3) read -p "Company: " c; python -m src.report --company "$c" ;;
  4) streamlit run app/streamlit_app.py ;;
esac
