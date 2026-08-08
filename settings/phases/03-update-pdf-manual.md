# D-003: 第2弾アップデート - 製品マニュアル取り込み（PDF）

| 項目 | 値 |
|---|---|
| フェーズ | 第2弾アップデート |
| ステータス | 実装済み |
| 作成日 | 2026-06-19 |
| 実装日 | 2026-07-08 |
| 前提 | [D-001 プロトタイプ](01-prototype.md)、[D-002 第1弾](02-update-eml-reader.md) が実装済みであること |

## 1. ゴール

PDF形式の製品マニュアルをRAGに取り込み、マニュアルに記載のある質問にも正確に回答できるようにする。

### スコープ内

- PDFファイルからのテキスト抽出
- 複数PDFファイルの一括処理
- チャンク分割 → Embedding → ChromaDB登録
- メタデータ付与（ファイル名、ページ番号）
- 回答生成時にマニュアル参照箇所の表示

### スコープ外

- PDF内の画像・図表の解析 → 将来検討
- OCR（スキャンPDF）→ 将来検討
- Word/HTML形式のマニュアル → 将来検討

## 2. アーキテクチャ差分

プロトタイプからの追加・変更箇所のみ記載する。

```
            ┌─────────────────────────┐
  新規追加 → │ PDFリーダー              │
            │ (etl/pdf_reader.py)     │
            └─────────┬───────────────┘
                      │ 抽出されたテキスト（ページ単位）
                      ▼
            ┌─────────────────────────┐
  既存     → │ PIIマスキング            │  ← 変更なし
            │ (masking/service.py)    │
            └─────────┬───────────────┘
                      ▼
            ┌─────────────────────────┐
  既存     → │ Embedding + ChromaDB    │  ← メタデータ拡張
            │ (rag/index_service.py)  │
            └─────────────────────────┘
```

## 3. 詳細設計

### 3.1 PDFテキスト抽出

Python の `pymupdf`（PyMuPDF）を使用する。

```python
@dataclass
class ExtractedPage:
    file_name: str         # PDFファイル名
    page_number: int       # ページ番号（1始まり）
    text: str              # 抽出されたテキスト
```

#### 抽出処理

1. `pymupdf` でPDFを開く
2. ページごとにテキストを抽出
3. 空白ページはスキップ
4. ヘッダー・フッター（ページ番号等）の除去は簡易的に行う（正規表現）

### 3.2 チャンク分割

マニュアルは1ページが長いため、ページ単位ではなくチャンク分割する。

```python
CHUNK_SIZE = 512       # トークン数（既存と同じ）
CHUNK_OVERLAP = 50     # オーバーラップ（既存と同じ）
```

ページ境界をまたぐチャンクは、元のページ番号を範囲で記録する（例: `pages: "12-13"`）。

### 3.3 ChromaDB メタデータ

```python
metadata = {
    "source": "pdf_manual",           # ソース種別
    "file_name": "product_guide.pdf", # ファイル名
    "page": "12",                     # ページ番号（または "12-13"）
    "date": "2026-06-19T00:00:00",    # 登録日時
}
```

### 3.4 コレクション構成

既存の `support_emails` コレクションとは別に、マニュアル専用コレクションを作成する。

```python
COLLECTION_EMAILS = "support_emails"      # 既存
COLLECTION_MANUALS = "product_manuals"    # 新規
```

回答生成時は両コレクションを検索し、結果をマージして上位5件を使用する。

### 3.5 CLI拡張

```bash
# 単一PDF登録
docker compose exec app python -m src.main register --pdf path/to/manual.pdf

# ディレクトリ内の全PDF一括登録
docker compose exec app python -m src.main register --pdf-dir path/to/manuals/
```

### 3.6 参照元表示の拡張

回答生成結果に、参照したマニュアルのファイル名・ページ番号を表示する。

```
[回答]
パスワードのリセットは、管理画面の「ユーザー管理」から...

[参照元]
📄 product_guide.pdf (p.23)
📧 メール #456 (2026-05-10)
```

## 4. ディレクトリ差分

```
src/
├── etl/
│   ├── pdf_reader.py        # 新規: PDFテキスト抽出
│   └── eml_reader.py        # 変更なし
├── rag/
│   ├── index_service.py     # 更新: マニュアルコレクション対応
│   └── query_service.py     # 更新: 複数コレクション検索対応
├── main.py                  # 更新: --pdf / --pdf-dir オプション追加
└── config.py                # 更新: COLLECTION_MANUALS 設定追加
```

## 5. 追加依存パッケージ

```toml
dependencies = [
    # ... 既存 ...
    "pymupdf>=1.24",          # PDFテキスト抽出
]
```

## 6. 制約・注意点

- スキャンPDF（画像のみのPDF）はテキスト抽出できない（OCR非対応）
- 表・図のレイアウトが崩れたテキストは、チャンク品質が低下する可能性がある
- 大きなPDF（数百ページ）の初回登録は数分かかる場合がある
