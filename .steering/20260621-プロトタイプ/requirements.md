# 要求内容

## 概要

テキスト入力 → PIIマスキング → RAG登録 → CLIベースでローカルLLMが回答生成、という一連の流れを最小構成で動作確認する。

## 背景

カスタマーサポート担当者がメール対応にかける時間を削減するため、過去の問い合わせとマニュアルをAIが参照して回答ドラフトを自動生成するシステムを構築する。メールにPIIが含まれるため、マスキング→LLMの流れが必要。プロトタイプで基本動作を検証する。

## 実装対象の機能

### 1. PIIマスキング（MaskingService）
- テキストからPII（メールアドレス、電話番号、郵便番号、人名、住所）を自動検出・マスキング
- マスクトークンを元の値に復元（アンマスク）
- 単独で利用可能（RAG・LLMなしで動作）

### 2. RAGデータ登録（IndexService）
- テキストをマスキング → チャンク分割 → Embedding → ChromaDB登録
- メタデータ（日時、ソース種別）を付与

### 3. RAG回答生成（QueryService）
- 質問テキストで類似検索（上位5件）→ LLM回答生成 → アンマスク
- ローカルLLM（Ollama + Gemma 4 12B）で動作

### 4. CLIインターフェース
- `mask`: マスキング単独実行
- `register`: テキスト登録
- `ask`: 単発質問
- `chat`: 対話モード

### 5. Docker環境
- Dockerfile + compose.yaml でアプリをコンテナ化
- OllamaはホストOS上で動作

### 6. プロジェクト基盤
- pyproject.toml、.gitignore、.env.example、.dockerignore

## 受け入れ条件

### PIIマスキング
- [x] メールアドレスを正規表現で検出・マスキングできる
- [x] 電話番号を正規表現で検出・マスキングできる
- [x] 郵便番号を正規表現で検出・マスキングできる
- [x] 人名をGiNZA NERで検出・マスキングできる
- [x] マスキング結果をプレビュー表示できる
- [x] マスクトークンを元の値にアンマスクできる
- [x] `python -m src.main mask` で単独実行できる

### RAGデータ登録
- [x] テキストをマスキング→チャンク分割→Embedding→ChromaDB登録できる
- [x] 登録件数を確認できる

### RAG回答生成
- [x] 質問に対して類似の登録データを検索できる
- [x] LLMが参照データを踏まえた回答を生成できる
- [x] 回答内のマスクトークンがアンマスクされる
- [x] `python -m src.main ask` / `chat` で実行できる

### Docker環境
- [x] `docker compose build` でビルドできる
- [x] `docker compose up -d` で起動できる
- [x] コンテナ内からホストのOllamaに接続できる

## 成功指標

- 一連のフロー（登録→質問→回答）が動作すること
- マスキング結果が目視で妥当であること

## スコープ外

- .emlファイル読み取り → 第1弾
- PDFマニュアル取り込み → 第2弾
- WebアプリUI → 第3弾
- Zendesk API連携 → 第4弾
- クラウドLLM切替 → プロトタイプ検証後

## 参照ドキュメント

- `settings/product-requirements.md` - PRD
- `settings/functional-design.md` - 機能設計書
- `settings/architecture.md` - アーキテクチャ設計書
- `settings/01-prototype.md` - プロトタイプ設計書
