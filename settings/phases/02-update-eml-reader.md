# D-002: 第1弾アップデート - .emlファイル読み取り

| 項目 | 値 |
|---|---|
| フェーズ | 第1弾アップデート |
| ステータス | 作成中 |
| 作成日 | 2026-06-17 |
| 前提 | [D-001 プロトタイプ](01-prototype.md) が実装済みであること |

## 1. ゴール

.emlファイルを入力として受け取り、メール本文を自動抽出してRAGに登録できるようにする。手動テキスト入力の代わりに、ファイル指定で一括登録を可能にする。

### スコープ内

- .emlファイルのパース（ヘッダー + 本文抽出）
- 複数ファイルの一括処理（ディレクトリ指定）
- メールスレッドの「問い合わせ → 回答」ペア検出
- メタデータ抽出（日時・件名・送信元）をChromaDBに付与

### スコープ外

- Outlook直接接続（Microsoft Graph API） → 第3弾以降
- .msg形式（Outlook独自形式）のサポート → 必要に応じて後日
- 添付ファイルの内容読み取り → 将来検討

## 2. アーキテクチャ差分

プロトタイプからの追加・変更箇所のみ記載する。

```
            ┌─────────────────────┐
  新規追加 → │ EMLリーダー          │
            │ (etl/eml_reader.py) │
            └─────────┬───────────┘
                      │ 抽出されたメール本文
                      ▼
            ┌─────────────────────┐
  既存     → │ PIIマスキング        │  ← 変更なし
            │ (masking/pipeline)  │
            └─────────┬───────────┘
                      ▼
            ┌─────────────────────┐
  既存     → │ Embedding + ChromaDB│  ← メタデータ拡張
            │ (rag/indexer.py)    │
            └─────────────────────┘
```

## 3. 詳細設計

### 3.1 .emlファイルパーサー

Pythonの標準ライブラリ `email` を使用する（追加依存なし）。

```python
@dataclass
class ParsedEmail:
    subject: str               # 件名
    from_address: str          # 送信元
    to_address: str            # 送信先
    date: datetime             # 送信日時
    body: str                  # 本文（プレーンテキスト）
    message_id: str            # Message-ID
    in_reply_to: str | None    # In-Reply-To（スレッド追跡用）
    references: list[str]      # References（スレッド追跡用）
```

#### パース処理

1. `email.message_from_file()` でパース
2. マルチパートの場合は `text/plain` パートを優先抽出
3. `text/plain` がない場合は `text/html` を `BeautifulSoup` でテキスト化
4. 文字エンコーディングは `charset` ヘッダーから自動検出（デフォルト: UTF-8, ISO-2022-JP）
5. 引用部分（`>` で始まる行、`-----Original Message-----` 以降）を分離

### 3.2 スレッド検出

`In-Reply-To` / `References` ヘッダーを使い、同一スレッドのメールを紐付ける。

```python
@dataclass
class EmailThread:
    thread_id: str                    # 最初のMessage-IDをスレッドIDとする
    emails: list[ParsedEmail]         # 時系列順
    pairs: list[tuple[str, str]]      # (問い合わせ本文, 回答本文) のペア
```

#### ペア検出ロジック

1. スレッド内のメールを日時順にソート
2. 送信元アドレスのドメインで「顧客」と「サポート」を判別
   - サポート側ドメインは設定ファイルで指定（例: `@example.com`）
3. 顧客メール → 直後のサポートメール を1ペアとする

### 3.3 CLI拡張

```bash
# 単一ファイル登録
python -m src.main register --eml path/to/email.eml

# ディレクトリ一括登録
python -m src.main register --eml-dir path/to/emails/

# サポートドメイン指定（デフォルトは config.py で設定）
python -m src.main register --eml-dir ./emails/ --support-domain example.com
```

### 3.4 ChromaDB メタデータ拡張

プロトタイプの `source="manual"` に加え、以下を追加：

```python
metadata = {
    "source": "eml",                    # ソース種別
    "subject": "パスワードリセットについて",  # 件名
    "date": "2026-05-15T10:30:00",      # 送信日時
    "thread_id": "<abc123@example.com>", # スレッドID
    "role": "inquiry" | "response",     # 問い合わせ or 回答
}
```

## 4. ディレクトリ差分

```
src/
├── etl/
│   ├── __init__.py          # 新規
│   └── eml_reader.py        # 新規: .emlパーサー + スレッド検出
├── main.py                  # 更新: --eml / --eml-dir オプション追加
└── config.py                # 更新: SUPPORT_DOMAIN 設定追加
```

## 5. 追加依存パッケージ

```toml
dependencies = [
    # ... 既存 ...
    "beautifulsoup4>=4.12",    # HTML→テキスト変換用
]
```

## 6. 制約・注意点

- .eml ファイルのエンコーディングが不正な場合はスキップしてログ出力する
- 大量ファイル（1000件以上）の一括処理時はプログレスバー表示を検討
- 引用部分の分離は完璧ではない（メールクライアントごとに引用形式が異なるため）
