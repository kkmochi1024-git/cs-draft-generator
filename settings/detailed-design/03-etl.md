最終更新: 2026-07-15 / 対象: D-001〜D-004 実装時点 / 対象コード: src/etl/

[← README.md](README.md)

# 03. データ取り込み（src/etl/）

.emlファイルおよびPDFファイルから、RAG登録に必要なテキストとメタデータを抽出するモジュール群。`masking/`・`rag/` に依存しない独立モジュールであり、呼び出し元（[04-cli.md](04-cli.md)・[05-webui.md](05-webui.md)）が抽出結果を `IndexService` に渡す。

## 1. EmlReader（eml_reader.py）

.emlファイルのパース、スレッド検出、問い合わせ/回答ペア抽出を行う。

### データモデル

**ParsedEmail** — 1通のメールを表す

| フィールド | 型 | 意味 |
|---|---|---|
| `subject` | `str` | 件名 |
| `from_address` | `str` | Fromヘッダー |
| `to_address` | `str` | Toヘッダー |
| `date` | `datetime \| None` | Dateヘッダーのパース結果（失敗時は`None`） |
| `body` | `str` | 本文（テキスト化済み） |
| `message_id` | `str` | Message-IDヘッダー |
| `in_reply_to` | `str \| None` | In-Reply-Toヘッダー（デフォルト`None`） |
| `references` | `list[str]` | Referencesヘッダーを空白区切りで分割したリスト（デフォルト空リスト） |

**EmailThread** — スレッド化されたメール群

| フィールド | 型 | 意味 |
|---|---|---|
| `thread_id` | `str` | スレッドを一意に識別するID（後述） |
| `emails` | `list[ParsedEmail]` | スレッドに属するメール（日時昇順） |
| `pairs` | `list[tuple[str, str]]` | 検出された(問い合わせ本文, 回答本文)のペア一覧（デフォルト空リスト） |

### parse_file(path) -> ParsedEmail | None

- 責務: 単一の.emlファイルをパースする
- 入力: `.eml` ファイルパス
- 出力: `ParsedEmail`、パース不可時は `None`
- 処理の要点:
  - `email.message_from_binary_file(f, policy=email.policy.default)` でパース。例外発生時は警告ログを出し `None` を返す（不正なメール形式・I/Oエラー等、**パース失敗時のスキップ動作**の起点。なお文字コードの吸収は後述の `_decode_payload` のフォールバックチェーンが担い、そちらは例外を送出しない）
  - `_extract_body()` が `None` を返した場合（本文抽出不可）も `None` を返す
  - `Date` ヘッダーは `parsedate_to_datetime()` でパースし、失敗しても例外を握りつぶして `date=None` のまま処理を継続する
  - `References` ヘッダーは空白区切りで分割してリスト化する

### parse_directory(path) -> list[ParsedEmail]

- 責務: ディレクトリ内の全 `*.eml` ファイルをファイル名順にパースする
- 出力: パース成功した `ParsedEmail` のリスト（失敗ファイルは警告ログを出してスキップし、処理は継続する）
- 処理の要点: `.eml` が1件も見つからない場合は警告ログを出し空リストを返す

### detect_threads(emails, support_domain) -> list[EmailThread]

- 責務: メール群を `In-Reply-To`/`References` を辿ってスレッド単位にグループ化し、各スレッド内の問い合わせ/回答ペアを検出する
- 入力: `ParsedEmail` のリスト、サポート側メールドメイン（例: `example.com`）
- 出力: `EmailThread` のリスト
- 処理の要点:
  1. `Message-ID` をキーに全メールを索引化する（`by_id`。`message_id` が空のメールは索引に登録されない）
  2. 各メールについて `_find_thread_root()` でスレッドの起点（最初のMessage-ID）を求め、同一起点のメールを1グループにまとめる
  3. グループ内を日時昇順（`date` が `None` の場合は `datetime.min` 扱い）にソートする
  4. `_detect_pairs()` でスレッド内の問い合わせ/回答ペアを抽出する

### _extract_body(msg) -> str | None（プライベート）

- 責務: メールメッセージから本文を抽出する。**text/plain優先、なければtext/htmlをテキスト化**
- 処理の要点:
  - 非マルチパートの場合、`content_type` が `text/plain` ならそのままデコード、`text/html` なら `_html_to_text()` でテキスト化、それ以外は `None`
  - マルチパートの場合は `msg.walk()` で全パートを走査し、最初に見つかった `text/plain` を優先。`text/plain` が無ければ最初の `text/html` をテキスト化する

### _decode_payload(part) -> str | None（プライベート）

- 責務: MIMEパートのペイロードをデコードする
- 処理の要点: **エンコーディングのフォールバックチェーン** — パートの `charset` → `utf-8` → `iso-2022-jp` → `shift_jis` → `cp932` の順に `decode()` を試行し、全て失敗した場合は `utf-8` に `errors="replace"` を付けて強制デコードする（クラッシュさせない）

### _html_to_text(html) -> str（プライベート）

- 責務: **HTML→テキスト変換**
- 処理の要点: `BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)` でタグを除去する。`bs4` が未インストールの場合は警告ログを出し、HTMLをそのまま返す（タグ除去なし）

### _find_thread_root(em, by_id, visited=None) -> str（プライベート）

- 責務: スレッドの起点Message-IDを返す（`References` は先頭要素を直接採用、`In-Reply-To` は親メールを再帰的に辿る）
- 処理の要点: `references[0]`（最初のReferences値）を優先し、なければ `in_reply_to` から親メールを `by_id` で辿って再帰する。`visited` 集合で循環参照を検出し無限再帰を防止する。起点が見つからない場合は自身の `message_id`（それも空なら `id(em)` の文字列）を返す

### _detect_pairs(emails, support_domain) -> list[tuple[str, str]]（プライベート）

- 責務: **問い合わせ/回答ペア抽出**。時系列順のメール列から「顧客メール→直後のサポートメール」のペアを検出する
- 処理の要点:
  - `support_domain` は比較前に小文字化し先頭の `@` を除去する（大文字小文字を無視し、`@example.com` 形式で渡しても動作する）。送信元アドレスも小文字化して比較する
  - 先頭から2件ずつ走査し、`current` の送信元に `support_domain` を含まず（＝顧客）、`next_email` の送信元に `support_domain` を含む（＝サポート）場合にペアとして採用し、インデックスを2進める。条件を満たさない場合は1件だけ進めて次の組み合わせを試す

## 2. PdfReader（pdf_reader.py）

PyMuPDF（`fitz`）を用いてPDFからページ単位でテキストを抽出する。スキャンPDF（画像のみ）やOCRは対象外（D-003スコープ外）。

### データモデル

**ExtractedPage**

| フィールド | 型 | 意味 |
|---|---|---|
| `file_name` | `str` | PDFファイル名（拡張子含む） |
| `page_number` | `int` | ページ番号（1始まり） |
| `text` | `str` | 抽出・整形後のテキスト |

### parse_file(path) -> list[ExtractedPage]

- 責務: 単一PDFからページ単位でテキストを抽出する
- 入力: PDFファイルパス
- 出力: `ExtractedPage` のリスト
- 処理の要点:
  - `fitz.open(path)` に失敗した場合（不正なPDF等）は警告ログを出し空リストを返す（**抽出失敗時のスキップ動作**）
  - 各ページを `page.get_text()` で取得し `_clean_text()` で整形。整形後に空になったページ（空白ページ・画像のみページ）は**スキップ**する
  - ページ抽出中に例外が発生した場合、それまでに抽出済みのページを警告ログとともに返す（部分的な結果を保持）
  - `finally` で `doc.close()` を必ず実行する
  - 1ページも抽出できなかった場合は「空白またはスキャンPDFの可能性」の警告ログを出す

### parse_directory(path) -> list[ExtractedPage]

- 責務: ディレクトリ内の全 `*.pdf` をファイル名順に処理し、全ページを平坦なリストで返す
- 処理の要点: PDFが1件も見つからない場合は警告ログを出し空リストを返す。個別PDFの抽出に失敗した場合は警告ログを出してスキップし、処理は継続する

### _clean_text(text) -> str（プライベート）

- 責務: **整形ルール** — ヘッダー・フッター（ページ番号のみの行）を簡易的に除去し、連続する空行を圧縮する
- 処理の要点:
  - 正規表現 `_PAGE_NUMBER_LINE`（`^\s*[-–—]?\s*\d+\s*[-–—]?\s*$`）にマッチする行（例: `"12"`, `"- 12 -"`）を除去する
  - 各行の末尾空白を `rstrip()` する
  - 連続する空行が2行以上続く場合は1行に圧縮する
  - 前後の空白を `strip()` して返す

## 参照

- 呼び出し元・登録先: [02-rag.md](02-rag.md) の `IndexService.register()`（`.eml` 本文）/ `register_pages()`（`ExtractedPage`）
- CLIからの利用: [04-cli.md](04-cli.md) の `cmd_register`（`--eml`/`--eml-dir`/`--pdf`/`--pdf-dir`）
- WebUIからの利用: [05-webui.md](05-webui.md) の `sidebar.py`（`register_eml_bytes`/`register_pdf_bytes`）
