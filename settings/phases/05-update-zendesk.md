# D-005: 第4弾アップデート - Zendesk API連携

| 項目 | 値 |
|---|---|
| フェーズ | 第4弾アップデート |
| ステータス | 作成中 |
| 作成日 | 2026-06-17 |
| 前提 | [D-001](01-prototype.md)、[D-002](02-update-eml-reader.md)、[D-003](03-update-pdf-manual.md)、[D-004](04-update-web-ui.md) が実装済みであること |

> **前提**: 本フェーズでは、ヘルプデスクSaaSの代表例として Zendesk を対象に設計する。チケット・コメントをREST APIで取得できる同種のサービス（Freshdesk、Intercom、Help Scout 等）にも同じ構造で対応できる設計とし、SaaS固有の処理は ETL 層に閉じ込める。

## 1. ゴール

ヘルプデスクSaaS（本設計では Zendesk Support）からチケット（問い合わせ + 回答）を自動取得し、RAGに登録する。手動の.emlファイル取り込みを不要にし、定期的なデータ更新を実現する。

### スコープ内

- Zendesk API v2 によるチケット・コメント取得
- 差分取得（前回取得以降の新規・更新チケットのみ）
- WebアプリUIからの取得実行・進捗表示
- 定期バッチ取得（cron等による自動実行）

### スコープ外

- Zendesk への回答投稿（読み取り専用）
- Outlook / Microsoft Graph API 連携 → 将来検討
- リアルタイムWebhook連携 → 将来検討

## 2. Zendesk API 設計

### 2.1 認証

```python
# APIトークン認証（OAuth不要で最もシンプル）
ZENDESK_SUBDOMAIN = "yourcompany"        # {subdomain}.zendesk.com
ZENDESK_EMAIL = "agent@yourcompany.com"  # エージェントのメール
ZENDESK_API_TOKEN = "..."                # 管理画面で発行
```

`.env` に格納し、Git管理外とする。

### 2.2 使用エンドポイント

| エンドポイント | 用途 |
|---|---|
| `GET /api/v2/tickets` | チケット一覧取得 |
| `GET /api/v2/tickets/{id}/comments` | チケットのコメント（やり取り）取得 |
| `GET /api/v2/incremental/tickets` | 差分取得（Incremental Export API） |

### 2.3 データモデル

```python
@dataclass
class ZendeskTicket:
    ticket_id: int
    subject: str               # 件名
    status: str                # open / pending / solved / closed
    created_at: datetime
    updated_at: datetime
    tags: list[str]            # タグ（カテゴリ分類に利用）
    comments: list[ZendeskComment]

@dataclass
class ZendeskComment:
    comment_id: int
    author_role: str           # "end-user" | "agent" | "admin"
    body: str                  # コメント本文
    created_at: datetime
    public: bool               # 公開 / 内部メモ
```

## 3. 取得フロー

### 3.1 初回フル取得

```
Zendesk API (Incremental Export)
  → 全チケット取得（ページネーション対応）
  → チケットごとにコメント取得
  → 問い合わせ(end-user) / 回答(agent) のペア抽出
  → PIIマスキング
  → Embedding + ChromaDB登録
  → 最終取得タイムスタンプを保存
```

### 3.2 差分取得（2回目以降）

```
保存済みタイムスタンプ以降の更新チケットを取得
  → 既にChromaDBに登録済みのチケットは更新（delete + insert）
  → 新規チケットは追加
  → タイムスタンプを更新
```

#### タイムスタンプ管理

```python
SYNC_STATE_FILE = "data/zendesk_sync_state.json"

{
    "last_sync_at": "2026-06-17T10:00:00Z",
    "total_tickets_synced": 1523
}
```

### 3.3 レート制限対応

Zendesk API のレート制限: 700リクエスト/分（Professional プラン）

```python
# リトライ + バックオフ
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 60  # 429エラー時

# バッチサイズ
TICKETS_PER_PAGE = 100    # Incremental Export の最大値
```

## 4. アーキテクチャ差分

```
┌───────────────────────────────┐
│ Zendesk API                   │
│ ({subdomain}.zendesk.com)     │
└──────────┬────────────────────┘
           │ HTTPS
           ▼
┌───────────────────────────────┐
│ Zendesk クライアント  (新規)    │
│ (etl/zendesk.py)              │
│  - チケット取得                 │
│  - コメント取得                 │
│  - 差分管理                    │
│  - レート制限対応               │
└──────────┬────────────────────┘
           │ ZendeskTicket リスト
           ▼
┌───────────────────────────────┐
│ 既存パイプライン               │
│  - PIIマスキング               │
│  - Embedding + ChromaDB登録   │
└───────────────────────────────┘

┌───────────────────────────────┐
│ Streamlit UI (既存)           │
│  - Zendesk同期ボタン追加       │
│  - 同期状態表示追加             │
└───────────────────────────────┘
```

## 5. UI拡張

### サイドバーにZendesk連携セクションを追加

```
◆ Zendesk連携
  接続状態: ✅ 接続済み
  最終同期: 2026-06-17 10:00
  登録チケット数: 1,523件

  [今すぐ同期]  [設定]
```

### 同期実行中の表示

```
◆ Zendesk同期中...
  ████████░░ 80% (1,218 / 1,523 チケット)
  経過時間: 3分12秒
  [キャンセル]
```

## 6. CLI拡張

```bash
# 初回フル同期
python -m src.main sync-zendesk

# 差分同期
python -m src.main sync-zendesk --incremental

# 定期実行（crontab登録例: 毎日AM3時）
# 0 3 * * * cd /path/to/chatbot && .venv/bin/python -m src.main sync-zendesk --incremental
```

## 7. ディレクトリ差分

```
src/
├── etl/
│   ├── zendesk.py           # 新規: Zendesk APIクライアント + 同期ロジック
│   └── eml_reader.py        # 変更なし
├── app/
│   └── components/
│       └── sidebar.py       # 更新: Zendesk連携セクション追加
├── main.py                  # 更新: sync-zendesk コマンド追加
└── config.py                # 更新: Zendesk設定項目追加
data/
└── zendesk_sync_state.json  # 新規: 同期状態管理（Git管理外）
```

## 8. 追加依存パッケージ

```toml
dependencies = [
    # ... 既存 ...
    "httpx>=0.27",        # Zendesk API呼び出し（非同期対応）
]
```

## 9. 環境変数

`.env` に追加：

```env
ZENDESK_SUBDOMAIN=yourcompany
ZENDESK_EMAIL=agent@yourcompany.com
ZENDESK_API_TOKEN=your_api_token_here
```

## 10. ChromaDB メタデータ拡張

```python
metadata = {
    "source": "zendesk",                  # ソース種別
    "ticket_id": 12345,                   # チケットID
    "subject": "パスワードリセットについて",  # 件名
    "date": "2026-05-15T10:30:00Z",       # 作成日時
    "status": "solved",                   # チケットステータス
    "tags": "password,account",           # タグ（カンマ区切り文字列）
    "role": "inquiry" | "response",       # 問い合わせ or 回答
}
```

## 11. 制約・注意点

- Zendesk APIトークンには適切な権限（チケット読み取り）が必要
- 初回フル同期はチケット数に応じて数十分〜数時間かかる可能性がある
- 内部メモ（`public: false`）は取り込むかどうかを設定で切替可能にする
- 削除済みチケットの扱い: Zendesk側で削除されたチケットはChromaDBから自動削除しない（手動クリーンアップ）
