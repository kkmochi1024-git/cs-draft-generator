# アーキテクチャ設計書

## アーキテクチャ概要

モジュラーモノリス＋Dockerコンテナ構成。アプリケーションは1コンテナ内で動作し、ローカルLLM（Ollama）はホストOS上で動作する。

```
┌─ Docker コンテナ ──────────────────────────────────────┐
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ CLI / WebアプリUI                                  │  │
│  └──────┬────────────────────────┬───────────────────┘  │
│         │                        │                     │
│         ▼                        ▼                     │
│  ┌──────────────┐    ┌───────────────────────────┐     │
│  │ MaskingService│    │ RAG Service               │     │
│  │ (単独利用可)  │    │  IndexService             │     │
│  │              │    │  QueryService             │     │
│  └──────────────┘    └────────────┬──────────────┘     │
│                                   │                    │
│  ┌──────────────┐    ┌────────────▼──────────────┐     │
│  │ ETL          │    │ ChromaDB                  │     │
│  │ eml_reader   │    │  support_emails           │     │
│  │ pdf_reader   │    │  product_manuals          │     │
│  │ zendesk      │    └───────────────────────────┘     │
│  └──────────────┘                                      │
│                                                        │
└───────────────────────────────────┬────────────────────┘
                                    │ HTTP
                                    ▼
                       ┌─────────────────────┐
                       │ ホスト OS            │
                       │ Ollama              │
                       │  gemma4:12b (LLM)   │
                       │  nomic-embed-text   │
                       └─────────────────────┘
```

## 技術スタック

| レイヤー | 技術 | 選定理由 |
|---|---|---|
| 言語 | Python 3.11+ | AI/MLエコシステムが豊富 |
| RAGフレームワーク | LangChain | Ollama/Claude両対応、ドキュメント充実 |
| Vector DB | ChromaDB | Pythonネイティブ、軽量、インストール容易 |
| PIIマスキング | spaCy + GiNZA + 正規表現 | ローカル完結、日本語NER対応 |
| Embedding | nomic-embed-text (Ollama) | ローカル完結、多言語対応 |
| LLM（ローカル） | Ollama + Gemma 4 12B (Q4) | 16GB RAM/CPUで動作、日本語品質が実用レベル |
| LLM（クラウド） | Claude API (claude-sonnet-4-6) | 高品質、マスキング後のテキストのみ送信 |
| UI | Streamlit（第3弾） | プロトタイプから運用まで対応、チャットUI標準対応 |
| PDF抽出 | PyMuPDF | 高速、レイアウト保持、純Python |
| HTTP通信 | httpx | Zendesk API用、非同期対応 |
| コンテナ | Docker + Docker Compose | クロスプラットフォーム、環境差異を排除 |

### コンテナビルド方針

- GiNZAモデル（ja_ginza）はDockerイメージのビルド時にダウンロードしてイメージに含める（コンテナ起動時間の短縮のため）

## コンポーネント設計

### MaskingService

**責務**: PIIの検出・マスキング・復元
**外部依存**: なし（自己完結、単独利用可能）
**実装の要点**:
- 正規表現（第1層）→ GiNZA NER（第2層）の順で処理
- マッピングテーブルはセッション単位で生成・破棄

### IndexService

**責務**: テキストのチャンク分割・Embedding生成・ChromaDB登録
**依存**: MaskingService, Ollama (nomic-embed-text)
**実装の要点**:
- support_emails と product_manuals の2コレクションを管理
- ソース種別（manual / eml / pdf_manual / zendesk）をメタデータで区別

### QueryService

**責務**: 類似検索・LLM回答生成・アンマスク
**依存**: MaskingService, Ollama (gemma4:12b) or Claude API
**実装の要点**:
- 両コレクションを横断検索し、上位5件をマージ
- LLMバックエンドは環境変数で切替可能（依存性注入）

### ETLモジュール群

**責務**: 外部データソースからのテキスト抽出
- `eml_reader`: .emlファイルパース、スレッド検出、問い合わせ/回答ペア抽出
- `pdf_reader`: PDFテキスト抽出（ページ単位）
- `zendesk`: Zendesk API v2によるチケット・コメント取得、差分同期

## データフロー

### データ登録フロー

```
入力ソース（テキスト / .eml / PDF / Zendesk）
  → ETL（テキスト抽出）
  → MaskingService.mask()（PII除去）
  → チャンク分割（512トークン、オーバーラップ50）
  → Embedding生成（nomic-embed-text via Ollama）
  → ChromaDB格納（メタデータ付き）
```

### 回答生成フロー

```
ユーザーの質問
  → MaskingService.mask()（質問のPII除去）
  → ChromaDB類似検索（2コレクション横断、上位5件）
  → プロンプト構築（システムプロンプト + 参照情報 + 質問）
  → LLM回答生成（Ollama or Claude API）
  → MaskingService.unmask()（回答のPII復元）
  → 回答 + 参照元を返却
```

## エラーハンドリング戦略

| 分類 | 例 | 対処方針 |
|---|---|---|
| Ollama接続不可 | Ollama未起動 / ポート不通 | エラーメッセージで接続先URLと起動手順を案内 |
| GiNZAモデル未ロード | ja_ginza未インストール | 正規表現のみで処理し警告を出力 |
| ChromaDB書き込み失敗 | ディスク容量不足 | エラーを伝播、登録処理を中断 |
| .eml パース失敗 | 不正なエンコーディング | 該当ファイルをスキップしログ出力 |
| PDF テキスト抽出失敗 | スキャンPDF | 該当ファイルをスキップしログ出力 |
| Zendesk API レート制限 | 429エラー | リトライ（60秒待機、最大3回） |

## テスト戦略

### ユニットテスト
- MaskingService: 各PIIパターンの検出・マスキング・復元
- RegexMasker: 正規表現パターンごとの検出精度
- NerMasker: GiNZA NERの検出精度（人名・住所）

### 統合テスト
- データ登録 → 検索 → 回答生成の一連のフロー
- .eml / PDF の読み取り → 登録 → 検索

## 依存ライブラリ

| ライブラリ | バージョン | 用途 |
|---|---|---|
| langchain | >=0.3 | RAGフレームワーク |
| langchain-community | >=0.3 | コミュニティ統合 |
| langchain-ollama | >=0.3 | Ollama連携 |
| chromadb | >=0.5 | Vector DB |
| spacy | >=3.7 | NLP基盤 |
| ginza | >=5.2 | 日本語NER |
| ja-ginza | >=5.2 | GiNZAモデル |
| pymupdf | >=1.24 | PDFテキスト抽出 |
| beautifulsoup4 | >=4.12 | HTMLメール→テキスト変換 |
| httpx | >=0.27 | Zendesk API通信 |
| streamlit | >=1.38 | WebアプリUI（第3弾） |

## セキュリティ考慮事項

- PIIを含む生データはChromaDBに格納しない（マスキング済みのみ）
- マスキングマッピングは揮発性（ログ・キャッシュに書き出さない）
- クラウドLLM利用時はマスキング済みテキストのみ送信
- APIキー・トークンは `.env` で管理、Gitにコミットしない

## パフォーマンス考慮事項

- Embedding生成: 1チャンクあたり1秒以内
- ChromaDB類似検索: 1秒以内
- 回答生成（ローカル）: 1〜2分（Gemma 4 12B (Q4) / CPU / 16GB RAM）
- 回答生成（クラウド）: 10秒以内

## 将来の拡張性

- MaskingServiceは単独利用可能な設計のため、他プロジェクトへの転用が容易
- 各サービスは依存性注入で疎結合のため、将来のマイクロサービス化にも対応可能
- ChromaDBからの移行が必要になった場合、IndexService/QueryServiceの内部実装のみ変更すればよい
