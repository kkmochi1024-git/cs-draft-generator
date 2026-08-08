# リポジトリ構造定義書

> **注記**: 本ドキュメントは現行構成を記載し、未実装のターゲット項目には `(未実装)` を付す。
> README の「フォルダ構成」はトップレベルの概要のみを扱い、ファイル単位の詳細は本ドキュメントを正とする。

## ディレクトリ構造

```
cs-draft-generator/
├── .claude/                   # Claude Code プロジェクト設定
│   ├── settings.json          #   権限設定
│   ├── git-sync-policy.md     #   /git-sync のリポジトリ別ポリシー（Git管理外）
│   ├── review-criteria.md     #   /review-doc のレビュー観点表（Git管理外）
│   └── skills/                #   プロジェクトローカルスキル
│       ├── save-chat/         #     チャット履歴保存
│       └── log-app-change/    #     変更履歴記録
├── settings/                  # 設計書・仕様書
│   ├── INDEX.md               #   設計書インデックス
│   ├── detailed-design/       #   詳細設計書（現行実装スナップショット、モジュール別）
│   │   ├── README.md          #     全体構成・シーケンス図・入口
│   │   ├── 01-masking.md      #     PIIマスキング
│   │   ├── 02-rag.md          #     RAGパイプライン
│   │   ├── 03-etl.md          #     データ取り込み（eml/PDF）
│   │   ├── 04-cli.md          #     CLI・設定管理
│   │   └── 05-webui.md        #     WebUI（Streamlit）
│   ├── phases/                #   フェーズ別設計書
│   │   ├── 01-prototype.md    #     プロトタイプ設計書
│   │   ├── 02-update-eml-reader.md # 第1弾（.eml読み取り）
│   │   ├── 03-update-pdf-manual.md # 第2弾（PDFマニュアル）
│   │   ├── 04-update-web-ui.md #    第3弾（WebアプリUI）
│   │   ├── 05-update-zendesk.md #   第4弾（Zendesk連携）
│   │   ├── 06-update-llm-switch.md # 第5弾（生成LLMマルチプロバイダ切替）
│   │   └── 07-update-embedding-switch.md # 第6弾（Embedding切替）
│   ├── product-requirements.md #  PRD
│   ├── functional-design.md   #   機能設計書
│   ├── architecture.md        #   アーキテクチャ設計書
│   ├── repository-structure.md #  本ドキュメント
│   ├── development-guidelines.md # 開発ガイドライン
│   └── glossary.md            #   用語集
├── src/
│   ├── __init__.py
│   ├── main.py                # CLIエントリポイント（mask / register / ask / chat）
│   ├── config.py              # 設定値の一元管理
│   ├── masking/               # PIIマスキング（単独利用可）
│   │   ├── __init__.py        #   MaskingServiceを公開
│   │   ├── service.py         #   MaskingService本体
│   │   ├── regex_masker.py    #   正規表現ルール
│   │   ├── ner_masker.py      #   GiNZA NERマスキング
│   │   └── models.py          #   Entity, MaskingResult
│   ├── rag/                   # RAGパイプライン
│   │   ├── __init__.py        #   IndexService, QueryServiceを公開
│   │   ├── index_service.py   #   IndexService（登録）
│   │   ├── query_service.py   #   QueryService（検索+回答）
│   │   ├── formatting.py      #   format_source（参照元メタデータの表示整形）
│   │   └── models.py          #   RegisterResult, AnswerResult, StreamingAnswer
│   ├── etl/                   # データ取り込み
│   │   ├── __init__.py        #   EmlReaderを公開
│   │   ├── eml_reader.py      #   .emlパーサー（ParsedEmail, EmailThread, EmlReader）
│   │   ├── pdf_reader.py      #   PDFテキスト抽出（ExtractedPage, PdfReader）
│   │   └── zendesk.py         #   Zendesk APIクライアント（第4弾・未実装）
│   └── app/                   # WebアプリUI（第3弾）
│       ├── __init__.py
│       ├── main.py            #   Streamlitメインページ
│       └── components/        #   UIコンポーネント
│           ├── __init__.py
│           ├── chat.py        #   チャットUI
│           ├── sidebar.py     #   サイドバー
│           └── masking_preview.py # マスキング確認
├── tests/
│   ├── __init__.py
│   ├── test_masking.py        # 正規表現マスキング・MaskingService
│   ├── test_ner_masker.py     # GiNZA NERマスキング
│   ├── test_eml_reader.py     # .emlパーサー
│   ├── test_pdf_reader.py     # PDFテキスト抽出
│   ├── test_rag.py            # IndexService / QueryService
│   ├── test_formatting.py     # 参照元表示の整形
│   └── fixtures/              # テスト用サンプルデータ（.eml）
├── scripts/                   # 補助スクリプト（アプリ本体には含めない）
│   └── inspect_db.py          #   ChromaDBの中身をホストから確認
├── docs/                      # 開発の記録
│   ├── changelog/             #   変更ログ
│   ├── chat-logs/             #   AIとのチャット履歴
│   └── command/               #   繰り返し使う手順書（テストデータ登録等）
├── docs-ignore/               # docs/ と同構成。レビュー前の作業記録を置く（Git管理外）
├── data/                      # 入力ファイル置き場（Git管理外。コンテナに /app/data でマウント）
│   └── chroma_db/             #   ChromaDB永続化
├── .steering/                 # 作業指示・タスク管理（ignore/ のみGit管理外）
├── Dockerfile                 # アプリコンテナ定義
├── compose.yaml               # Docker Compose定義
├── pyproject.toml             # Pythonプロジェクト設定
├── .env.example               # 環境変数テンプレート
├── .gitignore
├── .dockerignore
├── CLAUDE.md                  # Claude Code設定
└── README.md                  # セットアップ手順・フォルダ構成の概要
```

## ファイル命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| Pythonモジュール | snake_case | `eml_reader.py`, `index_service.py` |
| テストファイル | `test_` + 対象モジュール名 | `test_masking.py` |
| 設計書（フェーズ別） | `settings/phases/{番号}-{概要}.md` | `phases/01-prototype.md` |
| 設計書（詳細設計） | `settings/detailed-design/{番号}-{モジュール}.md` | `detailed-design/01-masking.md` |
| 設計書（マスター仕様書） | `{種別}.md`（ハイフン区切り） | `functional-design.md` |
| 変更ログ | `YYYY-MM-DD.md` | `2026-06-19.md` |
| チャット履歴 | `YYYY-MM-DD-{トピック}.md` | `2026-06-17-system-design.md` |
| 手順書 | `docs/command/{対象}.md` | `command/test-data-registration.md` |
| ステアリング | `.steering/YYYYMMDD-{機能名}/` | `.steering/20260708-web-ui/` |

## モジュール構成方針

- `masking/` は外部依存なしで自己完結する（単独利用可能）
- `rag/` は `masking/` に依存する（依存性注入）
- `etl/` はデータソースごとに1ファイルで完結する
- `app/` はバックエンド（masking, rag）の関数を直接呼び出す（API層は設けない）
- `scripts/` は開発者が直接実行する補助ツール置き場。`src/` からは import しない

## 設定ファイル一覧

| ファイル | 用途 | Git管理 |
|---|---|---|
| `pyproject.toml` | Python依存関係・プロジェクト設定 | Yes |
| `Dockerfile` | コンテナビルド定義 | Yes |
| `compose.yaml` | Docker Compose定義 | Yes |
| `.env.example` | 環境変数テンプレート（秘匿情報なし） | Yes |
| `.env` | 環境変数（APIキー等の秘匿情報） | **No** |
| `.gitignore` | Git除外設定 | Yes |
| `.dockerignore` | Dockerビルド除外設定 | Yes |
| `CLAUDE.md` | Claude Code設定 | Yes |
| `.claude/settings.json` | Claude Code の権限設定 | Yes |
| `.claude/git-sync-policy.md` | `/git-sync` のリポジトリ別ポリシー | **No** |
| `.claude/review-criteria.md` | `/review-doc` のレビュー観点表 | **No** |

## 環境別設定

| 環境 | 設定方法 | LLM_BACKEND | OLLAMA_BASE_URL |
|---|---|---|---|
| 開発（ホスト直接） | `.env` + venv | `local` | `http://localhost:11434` |
| 開発（Docker / Rancher Desktop） | `.env` + compose | `local` | `http://host.rancher-desktop.internal:11434` |
| 開発（Docker / Docker Desktop） | `.env` + compose | `local` | `http://host.docker.internal:11434` |
| 本番（Docker） | `.env` + compose | `local` | 同上 |

- `.env.example` の既定値は Rancher Desktop 向け。Docker Desktop 利用時は `OLLAMA_BASE_URL` を書き換える
- `LLM_BACKEND=cloud`（クラウドLLM切替）は D-006 で設計中であり、現行実装では `local` のみ有効
