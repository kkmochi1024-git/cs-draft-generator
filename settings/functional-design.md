# 機能設計書

## 機能概要

| 機能名 | 概要 | 優先度 | PRD要件 |
|---|---|---|---|
| PIIマスキング | テキストからPIIを検出・マスキング・復元 | P0 | PIIマスキング |
| RAGデータ登録 | マスキング済みテキストをChromaDBに登録 | P0 | RAGデータ登録 |
| RAG回答生成 | 類似検索＋LLMで回答ドラフトを生成 | P0 | RAG回答生成 |
| .eml読み取り | .emlファイルからメール本文を抽出・登録 | P1 | .emlファイル一括登録 |
| PDFマニュアル取り込み | PDFからテキスト抽出・登録 | P1 | 製品マニュアル取り込み |
| WebアプリUI | チャット形式のブラウザUI | P1 | WebアプリUI |
| Zendesk連携 | Zendesk APIでチケット自動取得・登録 | P1 | Zendesk API連携 |

## サービスインターフェース

各機能はサービスクラスとして独立したインターフェースを持つ。

### MaskingService（単独利用可）

**入力**: テキスト文字列
**出力**: MaskingResult（マスク済みテキスト + マッピングテーブル + 検出エンティティ一覧）

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `mask(text)` | `str` | `MaskingResult` | PIIを検出しマスキング |
| `unmask(text, mapping)` | `str, dict` | `str` | マスクトークンを元の値に復元 |

**内部構成**:
- RegexMasker: メールアドレス、電話番号、郵便番号、住所（都道府県名＋市区町村＋番地が揃ったもの）を正規表現で検出
- NerMasker: 人名、住所をGiNZA NERで検出。GiNZAが返す地名の直後に続く番地は、MaskingService が検出範囲に含める

**エラーケース**:
| ケース | 検出方法 | 対処 |
|---|---|---|
| 空文字列入力 | 入力チェック | 空のMaskingResultを返す |
| GiNZAモデル未ロード | spacy.load失敗 | 正規表現のみで処理し警告を出力 |

### IndexService

**依存**: MaskingService

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `register(text, metadata)` | `str, dict` | `RegisterResult` | テキストをマスキング→チャンク分割→ChromaDB登録 |
| `register_eml(path)` | `Path` | `RegisterResult` | .emlファイルを読み取り登録 |
| `register_pdf(path)` | `Path` | `RegisterResult` | PDFファイルを読み取り登録 |
| `get_stats()` | なし | `dict` | 登録件数等の統計情報 |

**処理フロー（register）**:
1. MaskingService.mask() でPIIマスキング
2. テキストをチャンク分割（512トークン、オーバーラップ50）
3. Ollama (nomic-embed-text) でEmbedding生成
4. ChromaDBに格納（メタデータ付き）

### QueryService

**依存**: MaskingService

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `ask(question)` | `str` | `AnswerResult` | 質問をマスキング→検索→LLM回答→アンマスク |

**処理フロー（ask）**:
1. MaskingService.mask() で質問のPIIマスキング
2. ChromaDB類似検索（support_emails + product_manuals、上位5件）
3. 検索結果＋質問をプロンプトに組み立て
4. Ollama (Gemma 4 12B) で回答生成
5. MaskingService.unmask() で回答内のマスクトークンを復元
6. AnswerResult（回答、参照元ドキュメント、マスキング結果）を返す

## データモデル

### エンティティ定義

#### MaskingResult

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| masked_text | str | Yes | マスク済みテキスト |
| mapping | dict[str, str] | Yes | トークン→元の値のマッピング |
| entities | list[Entity] | Yes | 検出されたエンティティ一覧 |

#### Entity

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| original | str | Yes | 元の文字列 |
| label | str | Yes | 種別（EMAIL / PHONE / ZIPCODE / ADDRESS = 正規表現由来の大文字、Person / Province / City / Country / Postal_Address = GiNZA NER由来のPascalCase） |
| token | str | Yes | 置換トークン（[EMAIL_1]等） |
| start | int | Yes | 開始位置 |
| end | int | Yes | 終了位置 |
| source | str | Yes | 検出元（regex / ner） |

#### RegisterResult

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| chunk_count | int | Yes | 登録チャンク数 |
| masking_result | MaskingResult | Yes | マスキング結果 |

#### AnswerResult

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| answer | str | Yes | アンマスク済み回答 |
| masked_answer | str | Yes | マスク状態の回答（デバッグ用） |
| source_documents | list[dict] | Yes | 参照した文書のメタデータ |
| masking_result | MaskingResult | Yes | 質問のマスキング結果 |

### ChromaDBコレクション構成

| コレクション | 格納データ | ソース |
|---|---|---|
| `support_emails` | 過去の問い合わせ＋回答 | 手動入力, .eml, Zendesk |
| `product_manuals` | 製品マニュアル | PDF |

## CLI インターフェース

```bash
# マスキング単独実行
python -m src.main mask "テキスト"

# データ登録（テキスト）
python -m src.main register

# データ登録（.eml）
python -m src.main register --eml path/to/file.eml
python -m src.main register --eml-dir path/to/emails/

# データ登録（PDF）
python -m src.main register --pdf path/to/manual.pdf
python -m src.main register --pdf-dir path/to/manuals/

# 単発質問
python -m src.main ask "質問テキスト"

# 対話モード
python -m src.main chat

# Zendesk同期
python -m src.main sync-zendesk
python -m src.main sync-zendesk --incremental
```

## 状態遷移

### LLMバックエンド状態

```
[ローカル (デフォルト)] ──── マスキング精度95%達成 ────▶ [クラウド]
        ▲                                                   │
        └──────── 手動切替 / 機密性が高い場合 ◀──────────────┘
```

切替は環境変数 `LLM_BACKEND` または WebアプリUIのトグルで行う。

### マスキングマッピングのライフサイクル

```
[生成] mask() 呼び出し時にマッピングテーブルを生成
  ↓
[利用] 回答生成後に unmask() でマッピングを参照して復元
  ↓
[破棄] CLIの1コマンド終了時 / WebアプリのHTTPリクエスト完了時に破棄
```

マッピングはメモリ上のみに保持し、ログ・キャッシュ・ファイルに書き出さない。

## エラーハンドリング

### IndexService

| ケース | 検出方法 | 対処 |
|---|---|---|
| Ollama未起動（Embedding生成失敗） | HTTP接続エラー | エラーメッセージで接続先URLと起動手順を案内。登録処理を中断 |
| ChromaDB書き込み失敗 | 例外捕捉 | エラーを伝播し、登録処理を中断。部分登録は行わない |
| .emlパース失敗（不正なエンコーディング） | デコードエラー | 該当ファイルをスキップしログ出力。他ファイルの処理は継続 |
| PDFテキスト抽出失敗（スキャンPDF） | 空テキスト検出 | 該当ファイルをスキップしログ出力。他ファイルの処理は継続 |

### QueryService

| ケース | 検出方法 | 対処 |
|---|---|---|
| Ollama未起動（LLM接続失敗） | HTTP接続エラー | エラーメッセージで接続先URLと起動手順を案内 |
| ChromaDBが空（登録データなし） | 検索結果0件 | 「参照データが登録されていません。先に register コマンドでデータを登録してください」と案内 |
| クラウドLLM APIキー未設定 | 認証エラー | 「ANTHROPIC_API_KEY が設定されていません。.env を確認してください」と案内 |
| クラウドLLM レート制限 | 429エラー | 60秒待機後にリトライ（最大3回） |

## ZendeskService

**依存**: MaskingService, IndexService

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `sync()` | なし | `SyncResult` | 全チケットをフル同期 |
| `sync_incremental()` | なし | `SyncResult` | 前回以降の差分のみ同期 |

**処理フロー（sync_incremental）**:
1. `data/zendesk_sync_state.json` から最終同期タイムスタンプを読み込む
2. Zendesk Incremental Export API で更新チケットを取得（ページネーション対応）
3. チケットごとにコメントを取得
4. `author_role` で問い合わせ（end-user）/ 回答（agent）を判別しペア化
5. 各ペアを `IndexService.register()` で登録（ソース種別: zendesk）
6. タイムスタンプを更新して保存

**エラーハンドリング**:

| ケース | 検出方法 | 対処 |
|---|---|---|
| APIトークン未設定・認証失敗 | 401エラー | エラーメッセージで `.env` の設定項目を案内 |
| レート制限（429） | HTTPステータス | 60秒待機後にリトライ（最大3回） |
| ネットワークエラー | 接続タイムアウト | リトライ（最大3回、指数バックオフ） |

## WebアプリUI（Streamlit）

### ページ構成

| ページ | パス | 概要 |
|---|---|---|
| チャット（メイン） | `src/app/main.py` | 質問入力 → 回答表示のチャットUI |
| サイドバー | `src/app/components/sidebar.py` | LLMバックエンド切替、データ管理、Zendesk同期 |
| マスキング確認 | `src/app/components/masking_preview.py` | マスキング結果のプレビュー・手動修正 |

### バックエンド接続方式

Streamlit UI はバックエンドのサービスクラスを直接呼び出す（API層は設けない）。

```python
# app/main.py でのサービス呼び出し
masking = MaskingService()
query = QueryService(masking_service=masking)
answer = query.ask(user_input)
```

### セッション状態管理

`st.session_state` で会話履歴を管理する。ブラウザリロードで消失する（永続化しない）。

```python
st.session_state.messages: list[dict]   # {"role": "user"|"assistant", "content": str}
st.session_state.llm_backend: str       # "local" | "cloud"
```
