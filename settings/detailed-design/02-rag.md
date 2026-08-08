最終更新: 2026-07-15 / 対象: D-001〜D-004 実装時点 / 対象コード: src/rag/

[← README.md](README.md)

# 02. RAGパイプライン（src/rag/）

チャンク分割・Embedding生成・ChromaDB登録（`IndexService`）と、類似検索・プロンプト構築・LLM呼び出し（`QueryService`）を担う。マスキング（[01-masking.md](01-masking.md)）とChromaDB/Ollamaの橋渡し役。

## 1. データモデル（models.py）

### RegisterResult

`IndexService.register()`/`register_pages()` の戻り値。

| フィールド | 型 | 意味 |
|---|---|---|
| `chunk_count` | `int` | 登録されたチャンク数 |
| `masking_result` | `MaskingResult` | 登録時に行われたマスキングの結果 |

### AnswerResult

`QueryService.ask()` の戻り値。

| フィールド | 型 | 意味 |
|---|---|---|
| `answer` | `str` | アンマスク済み（PII復元済み）の回答 |
| `masked_answer` | `str` | LLMが生成した直後のマスク済み回答 |
| `source_documents` | `list[dict]` | 参照元。各要素は `{"content": str, "metadata": dict}`（デフォルト空リスト） |
| `masking_result` | `MaskingResult` | 質問文のマスキング結果（デフォルトは空の `MaskingResult`） |

### StreamingAnswer

`QueryService.ask_stream()` の戻り値。UI側が `tokens` を逐次表示し、生成完了後に `mapping` で一括アンマスクすることを前提にした設計（マスクトークンがストリーミングのチャンク境界で分断される可能性があるため）。

| フィールド | 型 | 意味 |
|---|---|---|
| `is_empty` | `bool` | 検索結果が0件だったか |
| `guidance` | `str` | `is_empty=True` の場合の案内メッセージ |
| `source_documents` | `list[dict]` | 参照元（`is_empty=True` の場合は空） |
| `mapping` | `dict[str, str]` | 質問文マスキングのトークン対応表 |
| `tokens` | `Iterator[str]` | マスク済みチャンクを逐次yieldするイテレータ。実際のLLM呼び出しは最初の反復時に開始される |

## 2. IndexService（index_service.py）

テキスト/PDFページをマスキング・チャンク分割し、ChromaDBへ登録する。

### コンストラクタ

`IndexService(masking_service: MaskingService, collection_name: str | None = None)`

- `collection_name` 省略時は `config.COLLECTION_NAME`（`"support_emails"`）に登録する
- `OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)` でEmbeddingクライアントを生成（`EMBEDDING_MODEL` 既定値 `"nomic-embed-text"`）
- `RecursiveCharacterTextSplitter(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)`。既定値は `CHUNK_SIZE=512`、`CHUNK_OVERLAP=50`。チャンク長のカウントは**文字数ベース**（`length_function` 未指定のため Python の `len()` が使われる。トークン数ではない）
- `Chroma(collection_name=..., embedding_function=..., persist_directory=config.PERSIST_DIR)` でVector DBクライアントを生成（`PERSIST_DIR` は `<プロジェクトルート>/data/chroma_db`）

**コレクション構成**: `support_emails`（過去メール、既定コレクション）と `product_manuals`（製品マニュアルPDF）の2つ。`config.COLLECTION_EMAILS`（値 `"support_emails"`。既定の `COLLECTION_NAME` と同値）と `config.COLLECTION_MANUALS`（値 `"product_manuals"`）として定義される。

### register(text, metadata=None) -> RegisterResult

- 責務: テキストをマスキング→チャンク分割→ChromaDB登録する（主にメール本文・手入力テキスト向け）
- 入力: 登録対象テキスト、任意の追加メタデータ
- 出力: `RegisterResult`
- 処理の要点:
  - `masking.mask(text)` でマスキングし、`masked_text` を `_splitter.split_text()` でチャンク分割する
  - メタデータは `{"source": "manual", "date": <登録時刻のISO8601（UTC）>}` を基底とし、引数 `metadata` で上書き・追加する（呼び出し元が `source="eml"` 等で上書きする）
  - チャンクが0件（空テキスト等）の場合は登録処理をスキップし `chunk_count=0` で返す

### register_pages(pages, file_name, metadata=None) -> RegisterResult

- 責務: PDF等のページ単位テキスト（`list[ExtractedPage]`）を結合してマスキング・チャンク分割し、各チャンクの由来ページ番号をメタデータに付与して登録する
- 入力: `ExtractedPage` のリスト（[03-etl.md](03-etl.md) 参照）、ファイル名、任意の追加メタデータ
- 出力: `RegisterResult`
- 処理の要点:
  0. `pages` が空リストの場合は `chunk_count=0` で早期returnする
  1. 全ページを `"\n\n"` 区切りで結合し、各ページのマスキング前オフセット範囲（`page_spans`）を記録する
  2. 結合テキストを1回だけマスキングする（ページごとに個別マスキングしない）。マスキング後テキストが空白のみの場合も `chunk_count=0` で早期returnする
  3. マスキングによる文字数変化を補正するため、`_orig_to_masked_pos()` で各ページ境界をマスキング後テキスト上の位置に変換する
  4. マスキング後テキストをチャンク分割し、各チャンクの占有範囲を `masked_text.find()` で特定した上で `_page_range_str()` によりページ番号（単一 `"12"` または範囲 `"12-13"`）を算出し、メタデータの `page` に格納する
  5. メタデータ基底は `{"source": "pdf_manual", "file_name": file_name, "date": <登録時刻>}`
  6. 分割器がテキストを改変してチャンクの検索位置が特定できない場合（`find()` が `-1`）は、全ページ範囲でフォールバックする

### get_stats() -> dict

- 責務: コレクションの登録済みドキュメント数を返す
- 出力: `{"total_documents": int}`
- 処理の要点: LangChain Chromaラッパーに `count()` の公開APIがないため、内部属性 `self._vectorstore._collection` を直接参照している（ライブラリ更新時に破損しうる実装上の注意点）

### _add_texts(chunks, metadatas)（プライベート）

- 責務: `vectorstore.add_texts()` を呼び出し、Ollama未起動時のエラーを分かりやすく変換する
- 処理の要点: 例外メッセージ（小文字化）に `"connect"` を含む、または**例外クラス名**（小文字化）に `"connection"` を含む場合、`RuntimeError`（接続先URLと起動コマンドの案内文）に変換して送出する

### _orig_to_masked_pos(orig_pos, entities) -> int（静的メソッド）

- 責務: マスキング前の文字位置を、マスキング後テキスト上の対応する位置に変換する
- 処理の要点: `orig_pos` より前にある各エンティティについて `len(token) - (end - start)`（トークン長と元テキスト長の差分）を累積する。位置がエンティティ内部に入る場合はエンティティの開始位置に丸める（ページ境界がPII内部に入ることは稀だが、その場合の安全策）

### _page_range_str(masked_page_spans, chunk_start, chunk_end) -> str（静的メソッド）

- 責務: チャンクの占有範囲と重なるページ番号群から表示用文字列を作る
- 処理の要点: 範囲が重なるページ番号の最小値・最大値を求め、単一ページなら `"12"`、複数ページにまたがれば `"12-13"` を返す。重なりがなければ空文字列

## 3. QueryService（query_service.py）

質問文のマスキング、コレクション横断検索、プロンプト構築、LLM呼び出し（同期/ストリーミング）、アンマスクまでを担う。

### コンストラクタ

`QueryService(masking_service: MaskingService, collection_names: list[str] | None = None)`

- `collection_names` 省略時は `[config.COLLECTION_EMAILS, config.COLLECTION_MANUALS]`（両コレクション横断検索が既定）
- 各コレクションごとに `Chroma` インスタンスを生成し `self._vectorstores` に保持
- `ChatOllama(model=config.MODEL_NAME, base_url=..., temperature=config.TEMPERATURE, num_predict=config.MAX_TOKENS)`。既定値: `MODEL_NAME="gemma4:12b"`, `TEMPERATURE=0.3`, `MAX_TOKENS=1024`

### ask(question) -> AnswerResult

- 責務: 質問に対する回答を同期的に生成する（CLI向け）
- 入力: 質問文（マスキング前）
- 出力: `AnswerResult`
- 処理の要点:
  1. 質問文にもPIIが含まれうるため、検索前に `masking.mask(question)` でマスキングする
  2. `_search()` でマスク済みクエリを検索。結果0件なら `_EMPTY_GUIDANCE`（「参照データが登録されていません。先に register コマンドでデータを登録してください」）を `answer` として即座に返す
  3. `_build_prompt()` でプロンプトを構築し `self._llm.invoke(prompt)` を呼び出す。接続エラーは `_wrap_connection_error()` で変換して送出する
  4. `response.content`（`AIMessage` オブジェクトの場合）または `str(response)`（バージョン差異で直接文字列が返る場合）を `masked_answer` とする
  5. `masking.unmask(masked_answer, masking_result.mapping)` で回答中のマスクトークンをPII値に復元し `answer` とする

### ask_stream(question) -> StreamingAnswer

- 責務: 回答をストリーミングで生成する（WebUI向け）
- 入力: 質問文
- 出力: `StreamingAnswer`
- 処理の要点:
  - 検索・質問マスキングは `ask()` と同様に同期実行し、`source_documents`/`mapping` を先に確定させてから返す
  - `tokens` は `_stream_tokens(prompt)` のジェネレータで、呼び出し側が実際に反復するまでLLM呼び出しは開始されない（遅延評価）
  - `ask()` と異なり、この時点ではアンマスクを行わない（呼び出し側が `mapping` を使って確定表示時にアンマスクする設計。[05-webui.md](05-webui.md) の `chat.py` 参照）

### _stream_tokens(prompt) -> Iterator[str]（プライベート）

- 責務: `ChatOllama.stream()` の応答をマスク済み文字列チャンクとして逐次yieldする
- 処理の要点: `AIMessageChunk.content`（または直接文字列）をyieldし、例外発生時は `_wrap_connection_error()` で変換して送出する

### _build_prompt(docs, masked_question) -> str（静的メソッド）

- 責務: 検索結果と質問文からLLMへのプロンプトを構築する
- 処理の要点: 各ドキュメントの `page_content` を `"\n\n---\n\n"` で結合して `config.SYSTEM_PROMPT` の `{context}` に埋め込み、末尾に `"\n\n## お客様の質問\n{masked_question}"` を追加する。`SYSTEM_PROMPT` は「参考情報に含まれない内容については『確認いたします』と回答する」旨の指示を含む固定文

### _search(masked_query) -> list（プライベート）

- 責務: 全コレクションを横断検索し、距離でマージした上位 `SEARCH_TOP_K` 件を返す
- 処理の要点:
  1. 各コレクションで `similarity_search_with_score(masked_query, k=config.SEARCH_TOP_K)`（`SEARCH_TOP_K=5`）を実行し、`(doc, distance)` のペアを集める
  2. 距離（小さいほど類似）昇順で全体をソートしてマージする
  3. `page_content` が同一のチャンクは重複排除する（複数コレクションから同一内容が返る場合を考慮）
  4. 上位 `SEARCH_TOP_K` 件に達した時点で打ち切る

### _wrap_connection_error(e) -> Exception（静的メソッド）

- 責務: Ollama接続エラーを分かりやすい `RuntimeError` に変換する。それ以外の例外はそのまま返す
- 処理の要点: `IndexService._add_texts()` と同じ判定ロジック（例外メッセージに `"connect"`、または例外クラス名に `"connection"` を含むか。いずれも小文字化して比較）

### _to_source_documents(docs) -> list[dict]（静的メソッド）

- 責務: 検索結果（LangChainの `Document` オブジェクト）をUI/CLI表示用の辞書に変換する
- 処理の要点: `page_content` の先頭200文字と `metadata` のみを保持する（全文は保持しない）

## 4. formatting.py

CLI（`main.py`）とWebUI（`app/`）で共通利用する参照元表示の整形関数。

### format_source(meta) -> str

- 責務: 検索結果のメタデータ（`dict`）を人間可読な1行の文字列に整形する
- 入力: `metadata` 辞書（`source`, `file_name`, `page`, `subject`, `date` 等）
- 出力: 整形済み文字列
- 出典表示ルール:
  - `source == "pdf_manual"`: `📄 {file_name} (p.{page})`。`page` が空文字列の場合はページ表記を省略し `📄 {file_name}` のみ
  - `source == "eml"`: `📧 {subject} ({date})`。`subject` が空なら `📧 メール`、`date` が空なら日付表記を省略
  - それ以外（`source` 不明時は `"unknown"`）: `{source} ({date})`。`date` が空なら `source` のみ

## 参照

- マスキングの詳細: [01-masking.md](01-masking.md)
- PDFページ抽出の詳細（`ExtractedPage`）: [03-etl.md](03-etl.md)
- 呼び出し元: [04-cli.md](04-cli.md)（`cmd_register`/`cmd_ask`/`cmd_chat`）、[05-webui.md](05-webui.md)（`sidebar.py`/`chat.py`）
