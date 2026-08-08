FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
COPY tests/ tests/

RUN pip install --no-cache-dir ".[dev]" && \
    pip install --no-cache-dir langchain-chroma && \
    python -c "import ja_ginza; import spacy; spacy.load('ja_ginza')" 2>/dev/null || true

EXPOSE 8501

# デフォルトはWebUI（D-004）。CUIは docker compose exec app python -m src.main ... で利用する
CMD ["streamlit", "run", "src/app/main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
