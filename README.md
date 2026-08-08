# CS Draft Generator

SaaS 製品のカスタマーサポート（メール対応）を効率化する、RAG ベースの回答ドラフト生成システム。

過去の問い合わせメールと製品マニュアルを参照して回答ドラフトを自動生成します。個人情報（PII）は **LLM に渡す前にローカルで自動マスキング**されるため、顧客情報を含むメールでも安全に AI を活用できます。

## 主な機能

| 機能 | 説明 | 状態 |
|---|---|---|
| PII マスキング | 正規表現＋GiNZA NER の2層で メール・電話・人名・住所等を検出し、回答生成後に復元 | ✅ |
| RAG 登録／回答生成 | マスキング済みテキストを ChromaDB に登録し、類似検索＋LLM で回答を生成 | ✅ |
| .eml 一括取り込み | メールファイルから問い合わせ/回答ペアを抽出して登録 | ✅ |
| PDF マニュアル取り込み | 製品マニュアルをページ単位で登録。回答時に参照ページを表示 | ✅ |
| Web アプリ UI | ChatGPT ライクなチャット画面（Streamlit）。ファイルアップロード・マスキング確認付き | ✅ |
| Zendesk 連携 | チケットの自動取り込み（設計 D-005） | 🚧 設計中 |
| クラウド LLM 切替 | Claude API への切替（設計 D-006。現在はローカル LLM のみ） | 🚧 設計中 |

## アーキテクチャ

```
┌─ Docker コンテナ ─────────────────────────┐      ┌─ ホスト OS ────────────┐
│  Streamlit WebUI / CLI                    │      │  Ollama               │
│    → MaskingService（PII検出・復元）        │ HTTP │   gemma4:12b（生成）    │
│    → IndexService / QueryService（RAG）    │─────▶│   nomic-embed-text     │
│    → ChromaDB（support_emails/manuals）    │      │   （Embedding）        │
└───────────────────────────────────────────┘      └───────────────────────┘
```

詳細は [settings/architecture.md](settings/architecture.md) を参照。

## 必要環境

- Docker（Docker Desktop / Rancher Desktop / Docker Engine）
- [Ollama](https://ollama.com/)（ホスト OS 上で実行）
- メモリ 16GB / CPU で動作（GPU 不要）
- macOS / Windows / Linux

## セットアップ

```bash
# 1. Ollama モデルの取得（ホスト OS）
ollama pull gemma4:12b
ollama pull nomic-embed-text

# 2. 環境変数の準備
cp .env.example .env
# OLLAMA_BASE_URL を環境に合わせて編集:
#   Rancher Desktop → http://host.rancher-desktop.internal:11434（デフォルト記載値）
#   Docker Desktop  → http://host.docker.internal:11434

# 3. ビルド・起動
docker compose build
docker compose up -d    # WebUI が http://localhost:8501 で起動
```

ポートは PII を扱うため **localhost のみにバインド**しています（LAN には公開されません）。

## 使い方

### WebUI（推奨）

`docker compose up -d` 後、ブラウザで http://localhost:8501 を開く。チャットで質問すると、参照元（📧 過去メール / 📄 マニュアルのページ）付きで回答ドラフトが生成されます。サイドバーからテキスト・.eml・PDF の登録が可能です。

### CLI

```bash
# PII マスキングのみ（RAG・LLM 不要）
docker compose exec app python -m src.main mask "山田太郎 yamada@example.com"

# データ登録（入力ファイルは ./data/ に置く → コンテナの /app/data にマウントされる）
docker compose exec app python -m src.main register                        # テキスト対話登録
docker compose exec app python -m src.main register --eml data/mail.eml    # .eml 単体
docker compose exec app python -m src.main register --eml-dir data/emails/ # .eml 一括
docker compose exec app python -m src.main register --pdf data/manual.pdf  # PDF マニュアル

# 回答生成
docker compose exec app python -m src.main ask "パスワードの再設定方法を教えてください"
docker compose exec -it app python -m src.main chat   # 対話モード
```

### ホスト直接実行（開発時）

```bash
pip install -e .
python -m spacy download ja_ginza
streamlit run src/app/main.py   # WebUI
pytest tests/                   # テスト
```

## テスト

```bash
docker compose exec app pytest tests/
docker compose exec app pytest tests/ --cov=src --cov-report=term-missing
```

## フォルダ構成

```
cs-draft-generator/
├── src/                     # アプリケーション本体
│   ├── main.py              #   CLI エントリポイント（mask / register / ask / chat）
│   ├── config.py            #   環境変数・設定値の一元管理
│   ├── masking/             #   PII マスキング（正規表現＋GiNZA NER による検出と復元）
│   ├── rag/                 #   RAG（ChromaDB への登録・類似検索・LLM 回答生成・出力整形）
│   ├── etl/                 #   データ取り込み（.eml パーサー・PDF テキスト抽出）
│   └── app/                 #   Streamlit WebUI（main.py と components/ の UI 部品）
├── tests/                   # pytest テスト一式（fixtures/ にサンプル .eml を格納）
├── scripts/                 # 補助スクリプト（inspect_db.py: ChromaDB の中身をホストから確認）
├── settings/                # 設計書・仕様書（入口は INDEX.md）
│   ├── phases/              #   フェーズ別設計書（プロトタイプ〜第6弾の差分設計）
│   └── detailed-design/     #   詳細設計書（現行実装のスナップショット、モジュール別）
├── docs/                    # 開発の記録
│   ├── changelog/           #   変更ログ（YYYY-MM-DD.md）
│   ├── chat-logs/           #   AI との設計議論・技術検討の記録
│   └── command/             #   テストデータ登録など、繰り返し使う手順書
├── data/                    # 入力ファイル置き場と ChromaDB 永続化領域（Git 管理外）
├── .steering/               # 作業計画・タスクリスト（機能開発分のみ Git 管理対象）
├── .claude/                 # Claude Code のプロジェクト設定・ローカルスキル
├── Dockerfile               # アプリコンテナ定義
├── compose.yaml             # Docker Compose 定義（ポートは localhost のみにバインド）
├── pyproject.toml           # Python プロジェクト設定・依存関係
├── .env.example             # 環境変数テンプレート
└── CLAUDE.md                # Claude Code 向けのプロジェクト指示
```

Git 管理外のもの: `.env`、`data/`、`.steering/ignore/`（機能開発と無関係な作業のステアリング）、`docs-ignore/`（レビュー前の作業記録）。

各ファイル単位の構成・命名規則は [settings/repository-structure.md](settings/repository-structure.md) を参照。

## ドキュメント

- 設計書インデックス: [settings/INDEX.md](settings/INDEX.md)（PRD・機能設計・アーキテクチャ・フェーズ別設計書）
- 開発ガイドライン: [settings/development-guidelines.md](settings/development-guidelines.md)
- 変更ログ: [docs/changelog/](docs/changelog/)

## データの取り扱い

- PII を含む生データ（メール実物・マニュアル実物）は `data/` に置く。**`data/` は Git 管理外**
- ChromaDB にはマスキング済みテキストのみ保存される
- マスキングの対応表（トークン→元の値）はメモリ上のみで保持され、永続化されない
- API キー等は `.env` で管理（Git 管理外）。新しい環境変数を追加したら `.env.example` も更新する
