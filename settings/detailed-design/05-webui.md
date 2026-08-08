最終更新: 2026-07-15 / 対象: D-001〜D-004 実装時点 / 対象コード: src/app/

[← README.md](README.md)

# 05. WebUI（src/app/）

Streamlit製のチャットUI。`streamlit run src/app/main.py` で起動する。バックエンド（`masking/`・`rag/`・`etl/`）のロジックはCLIと共有し、UI層にAPI層を挟まず直接呼び出す。

## 1. 画面構成（main.py）

### ページ構成

- `st.set_page_config(page_title="CS Draft Generator", page_icon="💬", layout="wide")`
- タイトル「💬 CS回答ドラフト生成」＋キャプション（過去メール対応履歴と製品マニュアルを参照して回答ドラフトを生成する旨）
- レイアウトはサイドバー（データ管理）＋メインエリア（チャット）の2ペイン構成

### get_services() -> tuple[MaskingService, QueryService]

- 責務: 重い初期化（GiNZAモデルロード、Embedding/LLMクライアント生成）をセッション間でキャッシュする
- 処理の要点: `@st.cache_resource` デコレータにより、Streamlitプロセス内で `MaskingService`/`QueryService` のインスタンスを使い回す（リクエストごとの再初期化を避ける）

### _init_session_state()（プライベート）

- 責務: セッション状態の初期化

### st.session_state で保持する状態

| キー | 型 | 内容 |
|---|---|---|
| `messages` | `list[dict]` | チャット履歴。各要素は `{"role": "user"/"assistant", "content": str, "sources"?: list[dict]}` |
| `register_msgs` | `list[str]` | データ登録結果メッセージの履歴（サイドバー表示用、先頭に`✅`/`⚠️`を含む） |

いずれもブラウザリロード・セッション終了で消失する（DB等への永続化は行わない）。

### main()

- 責務: WebUIのエントリポイント
- 処理の要点: `_init_session_state()` → `get_services()` → `render_sidebar(masking)` → `render_chat(query, masking)` の順に呼び出す。モジュールロード時に直接 `main()` を実行する（`if __name__ == "__main__"` ガードなし。`streamlit run` はスクリプトを直接実行するため）
- 補足: `streamlit run` はスクリプトのディレクトリを `sys.path[0]` に設定するため、モジュール冒頭で `_PROJECT_ROOT`（`Path(__file__).resolve().parents[2]`）を `sys.path` に明示的に追加し、`src` パッケージをimport可能にしている

## 2. サイドバー（sidebar.py）

登録の中核ロジック（`register_*_bytes`/`register_text`/`get_collection_counts`）はStreamlit非依存の純粋関数として実装し、UI関数（`render_sidebar`）から呼び出す構成になっている。アップロードファイルはPIIを含むため、一時ファイルは処理後に必ず削除する。

### register_pdf_bytes(data, file_name, masking) -> str

- 責務: PDFバイト列をマニュアルコレクションに登録する
- 入力: アップロードされたPDFのバイト列、ファイル名、`MaskingService`
- 出力: 結果メッセージ文字列（成功時は `✅` 接頭、抽出失敗時は `⚠️` 接頭）
- 処理の要点: `tempfile.NamedTemporaryFile` に書き出し → `PdfReader().parse_file()` → `IndexService(masking, collection_name=config.COLLECTION_MANUALS).register_pages()`。`finally` で一時ファイルを `unlink(missing_ok=True)` する

### register_eml_bytes(data, file_name, masking) -> str

- 責務: `.eml`バイト列をメールコレクションに登録する
- 処理の要点: PDF系と同様に一時ファイル経由で `EmlReader().parse_file()` → `IndexService(masking).register()`。メタデータに `source: "eml"`, `subject`, （あれば）`date` を付与する。パース失敗時は `⚠️` メッセージを返す

### register_text(text, masking) -> str

- 責務: テキストをメールコレクション（既定コレクション）に登録する
- 処理の要点: `IndexService(masking).register(text)` を呼ぶだけの薄いラッパー

### get_collection_counts(masking) -> dict[str, int]

- 責務: 両コレクションの登録済みチャンク数を取得する
- 出力: `{"emails": int, "manuals": int}`。取得失敗時（Chroma未初期化・接続エラー等）は該当ラベルに `-1` を設定する
- 処理の要点:
  - `label`/`name` のペア（`("emails", COLLECTION_EMAILS)`, `("manuals", COLLECTION_MANUALS)`）ごとに `IndexService.get_stats()` を呼び、例外は個別に捕捉して処理を継続する
  - `get_services()`（`@st.cache_resource`）と異なりキャッシュされず、呼び出しのたびにコレクションごとの `IndexService`（`OllamaEmbeddings`/`Chroma` クライアント）を新規生成する。Streamlit はチャット1往復ごとにスクリプト全体を再実行するため、`render_sidebar` 経由で件数取得もその都度発生する

### _run_registration(handler, *args)（プライベート）

- 責務: 登録ハンドラ関数を実行し、結果を `session_state.register_msgs` に積む。エラーはUIに表示してクラッシュさせない
- 処理の要点: `st.spinner("登録中...")` 内で実行。`RuntimeError`（Ollama接続エラー等）は `st.error()`、その他の例外も同様に捕捉して表示する

### _confirm_text_registration(text, masking)（プライベート、`@st.dialog`）

- 責務: **テキスト登録時のマスキング確認ステップ**。登録前に原文・マスキング結果・検出PII一覧を確認し、続行/キャンセルを選ばせる
- 処理の要点: `st.dialog("マスキング結果プレビュー")` のモーダルとして表示。原文を `st.text()` で表示後、`render_masking_result(masking.mask(text))`（本ファイル「4. マスキングプレビュー」参照）で結果を表示する。「このまま登録」ボタン押下で `_run_registration(register_text, text, masking)` を実行、「キャンセル」ボタンはいずれも `st.rerun()` でモーダルを閉じる

### render_sidebar(masking)

- 責務: サイドバー全体を描画する
- 処理の要点:
  - `.emlファイル`アップローダー（`type=["eml"]`）＋「.emlを登録」ボタン → `register_eml_bytes` を実行
  - `PDFマニュアル`アップローダー（`type=["pdf"]`）＋「PDFを登録」ボタン → `register_pdf_bytes` を実行
  - `テキスト登録`のテキストエリア＋「マスキング確認して登録」ボタン → `_confirm_text_registration` （モーダル経由、直接登録はしない）
  - **コレクション件数表示**: `get_collection_counts()` の結果を「📧 メール: N件」「📄 マニュアル: N件」の形式で表示（取得失敗時は「取得失敗」）
  - 登録結果メッセージは直近5件（`register_msgs[-5:]`）のみ表示し、`✅`接頭なら `st.success`、それ以外は `st.warning`

## 3. チャット（chat.py）

### _render_sources(sources)（プライベート）

- 責務: 参照元ドキュメント一覧を折りたたみ表示する
- 処理の要点: `sources` が空なら何も表示しない。`st.expander("📎 参照元ドキュメント")` 内で各ドキュメントを `format_source(metadata)` の1行＋本文抜粋（`content`）の `st.caption` で表示する

### _render_history()（プライベート）

- 責務: `session_state.messages` の全履歴を `st.chat_message` で再描画する
- 処理の要点: `assistant` ロールのメッセージのみ `sources` を併せて表示する

### _generate_answer(query_service, masking, question)（プライベート）

- 責務: ストリーミングで回答を生成・表示し、`session_state.messages` に追記する
- 入力: `QueryService`, `MaskingService`, 質問文
- 処理の要点（**ストリーミング表示・アンマスク・出典表示の流れ**）:
  1. `st.chat_message("assistant")` コンテキスト内で `query_service.ask_stream(question)` を呼ぶ。検索時点での接続エラー等は `st.error()` 表示のみで処理を打ち切る
  2. `streaming.is_empty` が真の場合は `streaming.guidance`（値は `query_service.py` の `_EMPTY_GUIDANCE` 定数。[02-rag.md](02-rag.md) 参照）をそのまま表示し履歴に追加して終了する
  3. `st.empty()` のプレースホルダに対し、`streaming.tokens` を1チャンクずつ `masked_full` に連結しながら `masked_full + "▌"`（生成中カーソル）を逐次 `markdown()` 表示する。この間はマスクトークンをそのまま表示する（未確定のため）
  4. 生成完了後、`masking.unmask(masked_full, streaming.mapping)` で一括アンマスクし、プレースホルダを確定表示に置き換える（マスクトークンがチャンク境界で分断される問題への対策として、逐次アンマスクはしない）
  5. `_render_sources()` で参照元を表示し、`session_state.messages` に `{"role": "assistant", "content": answer, "sources": ...}` を追加する
  6. ストリーミング中の例外も `st.error()` で捕捉し、UI全体をクラッシュさせない

### render_chat(query_service, masking)

- 責務: チャット画面全体を描画する
- 処理の要点: `_render_history()` → `st.chat_input()` で質問受付 → 質問があれば `session_state.messages` にユーザー発話を追加・即時表示 → `_generate_answer()` を呼ぶ

## 4. マスキングプレビュー（masking_preview.py）

### render_masking_result(result: MaskingResult)

- 責務: マスキング結果（マスク後テキスト＋検出PII一覧）をインライン表示する共通部品
- 入力: `MaskingResult`（[01-masking.md](01-masking.md)参照）
- 処理の要点:
  - `st.code(result.masked_text or "(空)", language=None)` でマスク後テキストを表示
  - 検出エンティティを `pandas.DataFrame` に変換し `st.dataframe()` で一覧表示。列は「トークン」「元の値」「種別」。`result.entities` が空の場合は一覧の代わりに `st.caption("PIIは検出されませんでした。")` を表示する
  - 「種別」列は `_LABEL_JA` 辞書（キー: `PERSON`/`EMAIL`/`PHONE`/`POSTAL`/`ADDRESS`）で日本語ラベルに変換を試み、辞書に無いキーは `entity.label` の値をそのまま表示する
  - **実装上の注意**: マスキング層が実際に生成するラベル値は `EMAIL`/`PHONE`/`ZIPCODE`（正規表現）と `Person`/`Province`/`City`/`Country`（GiNZA、大文字始まりの英語ラベル）であり（[01-masking.md](01-masking.md) 参照）、`_LABEL_JA` のキー（`PERSON`/`POSTAL`/`ADDRESS` 等の大文字スネーク風表記）とは `EMAIL`/`PHONE` 以外一致しない。そのため `Person`・`ZIPCODE`・`Province`/`City`/`Country` は日本語変換されず、ラベル文字列がそのまま表示される。設計書には実装どおりの挙動として記載する（コード修正は本作業のスコープ外）

## 参照

- `MaskingService`/`MaskingResult`/`Entity`: [01-masking.md](01-masking.md)
- `IndexService`/`QueryService`/`format_source`: [02-rag.md](02-rag.md)
- `EmlReader`/`PdfReader`: [03-etl.md](03-etl.md)
- 設定値: [04-cli.md](04-cli.md)（`config.py`）
- テスト: `src/app/` 配下を対象とした自動テストは現時点で存在しない（[README.md](README.md) 4章参照）。WebUI変更時は手動確認が必要
