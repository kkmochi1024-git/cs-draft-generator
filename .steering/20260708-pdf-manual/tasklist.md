# タスクリスト

## タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- 全てのタスクを `[x]` にすること
- 未完了タスク `[ ]` を残したまま作業を終了しない

---

## フェーズ1: 依存パッケージ

- [x] pyproject.toml に `pymupdf>=1.24` を追加
- [x] pymupdf をインストールし import できることを確認（1.28.0）

## フェーズ2: PDFリーダー

- [x] src/etl/pdf_reader.py を作成
  - [ ] `ExtractedPage` dataclass（file_name, page_number, text）
  - [ ] `PdfReader.parse_file(path)` → list[ExtractedPage]
  - [ ] `PdfReader.parse_directory(dir)` → list[ExtractedPage]
  - [ ] 空白ページスキップ・ヘッダー/フッター簡易除去
  - [ ] 不正PDF・存在しないファイルでクラッシュしない

## フェーズ3: RAGサービス更新

- [x] src/rag/index_service.py を更新
  - [x] コンストラクタに `collection_name` 引数を追加（未指定時 COLLECTION_NAME にフォールバック＝既存テスト互換）
  - [x] `register_pages(pages, file_name)` を追加（マスキング1回＋オフセット補正でページ範囲メタデータ付与）
- [x] src/rag/query_service.py を更新
  - [x] emails / manuals 両コレクションを検索しマージ（距離昇順・上位K・内容で重複排除）

## フェーズ4: CLI・参照元表示

- [x] src/main.py を更新
  - [x] register サブパーサに `--pdf` / `--pdf-dir` を追加
  - [x] `_register_pdf_file` / `_register_pdf_dir` ハンドラを実装
  - [x] 参照元表示で source=pdf_manual をファイル名・ページ整形（📄 file.pdf (p.23)）

## フェーズ5: テスト

- [x] tests/test_pdf_reader.py を作成（PyMuPDFでフィクスチャPDF動的生成）
  - [x] ページ抽出テスト
  - [x] 空白ページスキップテスト
  - [x] 不正/存在しないファイルテスト
  - [x] ディレクトリ一括テスト
  - [x] ページ範囲算出ロジックの純粋関数テスト（追加）

## フェーズ6: 品質チェックと修正

- [x] pytest tests/ が全てパスすることを確認（53 passed）
- [x] ruff check src/ でリントエラーがないことを確認（All checks passed）
- [x] register_pages をモックで実動作確認（ページ番号割当・PIIマスキング・オフセット補正）

## フェーズ7: ドキュメント更新

- [x] settings/INDEX.md の D-003 ステータスを「実装済み」に更新
- [x] settings/03-update-pdf-manual.md のステータスを「実装済み」に更新
- [x] /log-app-change を実行（docs/changelog/2026-07-08.md）
- [x] 実装後の振り返り（このファイルの下部に記録）

---

## 実装後の振り返り

### 実装完了日
2026-07-08

### 計画と実績の差分

**計画と異なった点**:
- `IndexService` の `collection_name` デフォルトを設計書の COLLECTION_EMAILS ではなく `COLLECTION_NAME` へのフォールバックとした。既存 `TestIndexService` が `mock_config.COLLECTION_NAME` を設定しており、COLLECTION_EMAILS に変えると Chroma に MagicMock が渡り既存テストが壊れるため。COLLECTION_NAME == COLLECTION_EMAILS == "support_emails" で値は同一。
- `QueryService` を `similarity_search` → `similarity_search_with_score` に変更（複数コレクションを距離でマージするため）。これに伴い既存 `TestQueryService` のモックを4箇所更新した。
- `register_pages` はマスキングを1回だけ行い、ページ境界オフセットをマスキングによる文字数変化で補正する方式を採用（当初はチャンクごとマスキングも検討したが、既存 register とセマンティクスを揃え、かつページ範囲を正確に保つため単一マスキング＋オフセット変換にした）。

**新たに必要になったタスク**:
- ページ範囲算出ロジック（`_page_range_str` / `_orig_to_masked_pos`）の純粋関数テストを追加。
- テストフィクスチャPDFのASCII化（PyMuPDF 既定フォント helv が日本語グリフを埋め込めず「·」になるため、抽出内容の検証はASCIIで実施）。

### 学んだこと

**技術的な学び**:
- PyMuPDF(fitz) の `page.insert_text` は既定フォントで CJK グリフを埋め込めない。日本語を含むフィクスチャPDFを作る場合は CJK フォント指定が必要。抽出機構の検証はASCIIで十分。
- マスキングで文字数が変わるため、ページ境界のオフセットは「手前のエンティティのトークン長差分の累積」で後付け補正できる（entities は start/end と token を持つため計算可能）。
- 複数コレクションをまたいで関連度順に統合するにはスコア（距離）が必須。`similarity_search` ではなく `similarity_search_with_score` を使う。

**プロセス上の改善点**:
- 実装前に既存テストのモック方法（何をパッチしているか）を確認したことで、後方互換の設計判断（COLLECTION_NAME フォールバック）を早期に決められた。

### 次回への改善提案
- register_pages の統合テスト（Chroma/Embeddings モックでの add_texts 引数検証）を正式なテストケースとして tests/ に追加する（今回はスモーク確認のみ）。
- 日本語PDFのE2E動作は Ollama 環境が必要なため未実施。Ollama 接続可能な環境で `register --pdf` → `ask` の実データ確認を行う。
- ヘッダー/フッター除去が「ページ番号のみの行」に限定的。実マニュアルで固定ヘッダー文字列が混入する場合は除去ルールの拡張を検討。
