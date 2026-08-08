# 設計書

## アーキテクチャ概要

モジュラーモノリス。3つのサービスクラスを依存性注入で組み立て、CLIから呼び出す。

```
CLI (main.py)
  ├── mask     → MaskingService.mask()
  ├── register → MaskingService.mask() → IndexService.register()
  ├── ask      → QueryService.ask() → MaskingService.unmask()
  └── chat     → ask のループ

MaskingService（自己完結）
  ├── RegexMasker（EMAIL, PHONE, ZIPCODE）
  └── NerMasker（Person, Location）

IndexService（MaskingService に依存）
  → チャンク分割 → Embedding(nomic-embed-text) → ChromaDB

QueryService（MaskingService に依存）
  → ChromaDB検索 → プロンプト構築 → Ollama(gemma4:12b)
```

## コンポーネント設計

### 1. masking/models.py — データクラス（Entity, MaskingResult）

### 2. masking/regex_masker.py — 正規表現PII検出
- PATTERNS辞書にパターン定義、finditerで位置情報保持、トークン番号を採番

### 3. masking/ner_masker.py — GiNZA NER PII検出
- spaCy nlpパイプラインを1回だけロード、Person/Locationのみ抽出

### 4. masking/service.py — RegexMasker + NerMasker統合
- 正規表現を先に適用→NERは正規表現マスク済みテキストに実行（二重検出防止）
- unmaskはマッピングテーブルの逆引き

### 5. rag/models.py — データクラス（RegisterResult, AnswerResult）

### 6. rag/index_service.py — マスキング→チャンク分割→Embedding→ChromaDB登録
- LangChain RecursiveCharacterTextSplitter、OllamaEmbeddings、Chroma

### 7. rag/query_service.py — 類似検索→プロンプト構築→LLM回答生成
- Chroma.similarity_search（上位5件）、OllamaLLM

### 8. config.py — 全設定値の一元管理（環境変数+デフォルト値）

### 9. main.py — CLIエントリポイント（argparse、サービス組み立て）

## 実装の順序

1. プロジェクト基盤（pyproject.toml, config.py, .gitignore, .env.example）
2. masking/models.py → regex_masker.py → ner_masker.py → service.py
3. test_masking.py
4. rag/models.py → index_service.py → query_service.py
5. main.py
6. Dockerfile + compose.yaml + .dockerignore
7. 品質チェック

## セキュリティ考慮事項

- PIIを含む生データをChromaDBに格納しない
- マスキングマッピングはメモリ上のみに保持
