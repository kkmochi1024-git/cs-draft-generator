import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:12b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

COLLECTION_NAME = "support_emails"
COLLECTION_EMAILS = "support_emails"
COLLECTION_MANUALS = "product_manuals"
PERSIST_DIR = str(PROJECT_ROOT / "data" / "chroma_db")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
SEARCH_TOP_K = 5

SUPPORT_DOMAIN = os.getenv("SUPPORT_DOMAIN", "")

TEMPERATURE = 0.3
MAX_TOKENS = 1024

SYSTEM_PROMPT = """あなたはカスタマーサポート担当者です。
以下の参考情報をもとに、お客様の質問に丁寧に回答してください。
参考情報に含まれない内容については「確認いたします」と回答してください。

## 参考情報
{context}
"""
