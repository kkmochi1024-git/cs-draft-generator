# D-004: 第3弾アップデート - GUIベース（Webアプリ）回答生成

| 項目 | 値 |
|---|---|
| フェーズ | 第3弾アップデート |
| ステータス | 実装済み |
| 作成日 | 2026-06-17 |
| 実装日 | 2026-07-08 |
| 最終更新 | 2026-07-08（D-003実装反映・React移行基準追記・LLM切替をD-006へ分離） |
| 前提 | [D-001](01-prototype.md)、[D-002](02-update-eml-reader.md)、[D-003](03-update-pdf-manual.md) が実装済みであること |

## 1. ゴール

CUIベースの回答生成をWebアプリ（ChatGPTライクなチャットUI）に置き換え、サポート担当者が直感的に使えるインターフェースを提供する。

### スコープ内

- チャット形式の対話UI（メッセージ入力 → 回答表示）
- 会話履歴の表示（セッション内）
- マスキング結果のプレビュー表示
- RAG参照元の表示（過去メール・PDFマニュアルの両方。D-003のファイル名・ページ番号表示に対応）
- .emlファイルのアップロード登録
- PDFマニュアルのアップロード登録（D-003機能のGUI化）

### スコープ外

- ユーザー認証・マルチテナント → 将来検討
- 回答の直接メール送信 → 将来検討
- 会話履歴のDB永続化 → 将来検討
- LLMバックエンド切替（ローカル / クラウド）のUI → [D-006](06-update-llm-switch.md) に分離（2026-07-08。バックエンド側のクラウド切替が未実装であり、UIトグルだけ先行させず実装とセットで扱うため）

## 2. 技術選定

### Streamlit vs FastAPI + React

| 観点 | Streamlit | FastAPI + React |
|---|---|---|
| 開発速度 | 速い | 遅い |
| UI自由度 | 制限あり | 高い |
| チャットUI | `st.chat_message` で対応可 | 自前実装 |
| ファイルアップロード | 標準対応 | 自前実装 |
| 将来のスケーラビリティ | 限定的 | 高い |

**判断: Streamlit を採用する。** 社内ツールであり、利用者は数名〜十数名規模。チャットUIは `st.chat_message` で十分に実現可能。将来スケールが必要になった時点で FastAPI + React への移行を検討する。

### React + TypeScript への移行判断基準（2026-07-08 追記）

Streamlit 継続の根拠と、移行を再検討すべき条件を記録として残す。

**Streamlit を維持する理由**:

- バックエンドに API 層が存在しない。React 化には FastAPI 等の API 新設（エンドポイント設計・CORS・ストリーミング配信・エラーハンドリング）が必要になり、実装量は体感 3〜5 倍になる
- 本フェーズの要件は Streamlit 標準部品と 1:1 で対応する（`st.chat_message` / `st.chat_input` / `st.file_uploader` / `st.expander` / `st.dialog` + `st.data_editor` / `st.write_stream`）
- Python 単一ツールチェーンを維持でき、npm・bundler・ESLint 等の二重保守を避けられる

**以下のいずれかが現実になった時点で FastAPI + React (TypeScript) への移行を検討する**:

1. ユーザー認証・マルチテナントが要件化した
2. 社外・顧客向けに公開することになった
3. マスキング結果のインライン編集など、Streamlit の再実行（rerun）モデルでは実現が困難なリッチな操作性が要件になった
4. D-005（Zendesk連携）以降のフェーズで API 層を新設することになった（バックエンドAPIが存在する状態になるため、最も自然な移行タイミング）
5. 同時利用者数が数十名規模に増え、Streamlit のセッション性能が問題になった

移行時は「Streamlit を捨てて作り直す」のではなく、まず API 層（FastAPI）を切り出し、Streamlit をそのAPIのクライアントに改修してから React に置き換える二段階を推奨する（バックエンドロジックの回帰リスクを分離するため）。

## 3. 画面設計

### 3.1 メイン画面（チャット）

```
┌─────────────────────────────────────────────────┐
│  [サイドバー]              │  [メインエリア]        │
│                           │                      │
│  ◆ データ管理             │  ┌──────────────────┐│
│  [.emlアップロード]        │  │ 🤖 回答:          ││
│  [PDFアップロード]         │  │ パスワードのリセット││
│  [テキスト登録]            │  │ は以下の手順で...  ││
│                           │  │                  ││
│  ◆ マスキング確認          │  │ 📎 参照元:        ││
│  [最新のマスキング結果]     │  │ 📧 メール #123    ││
│                           │  │ 📄 guide.pdf p.12 ││
│  登録済みチャンク数:       │  └──────────────────┘│
│  📧 メール 142件           │                      │
│  📄 マニュアル 87件        │  ┌──────────────────┐│
│                           │  │ 👤 質問:          ││
│                           │  │ パスワードの     ││
│                           │  │ リセット方法は？  ││
│                           │  └──────────────────┘│
│                           │                      │
│                           │  ┌──────────────────┐│
│                           │  │ 💬 メッセージ入力  ││
│                           │  │ [________________]││
│                           │  │          [送信]   ││
│                           │  └──────────────────┘│
└─────────────────────────────────────────────────┘
```

### 3.2 マスキング確認モーダル

```
┌──────────────────────────────────────────┐
│  マスキング結果プレビュー                   │
│                                          │
│  [原文]                                   │
│  山田太郎様(yamada@example.com)より...     │
│                                          │
│  [マスキング後]                            │
│  [PERSON_1]様([EMAIL_1])より...           │
│                                          │
│  [検出されたPII]                           │
│  ┌────────────┬──────────┬─────────┐     │
│  │ トークン    │ 元の値    │ 種別    │     │
│  ├────────────┼──────────┼─────────┤     │
│  │ [PERSON_1] │ 山田太郎  │ 人名    │     │
│  │ [EMAIL_1]  │ yamada@..│ メール  │     │
│  └────────────┴──────────┴─────────┘     │
│                                          │
│  [手動修正] [このまま続行] [キャンセル]      │
└──────────────────────────────────────────┘
```

## 4. アーキテクチャ差分

```
┌─────────────────────────────┐
│ Streamlit UI (app/main.py)  │  ← 新規
│  - チャット画面              │
│  - サイドバー（設定・管理）   │
│  - マスキング確認モーダル     │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 既存バックエンド              │  ← ほぼ変更なし
│  - masking/service           │     （query_service のみ
│  - rag/query_service         │       ストリーミング対応で更新）
│  - rag/index_service         │
│  - etl/eml_reader            │
│  - etl/pdf_reader            │
└─────────────────────────────┘
```

バックエンドのロジックは変更しない。Streamlit UI はバックエンドの関数を直接呼び出す（API層は設けない）。

## 5. 主要な実装ポイント

### 5.1 チャットセッション管理

```python
# Streamlit session_state で会話履歴を管理
if "messages" not in st.session_state:
    st.session_state.messages = []

# メッセージ追加
st.session_state.messages.append({
    "role": "user",
    "content": user_input,
})
```

### 5.2 ストリーミング表示

Ollama はストリーミングレスポンスに対応しているため、回答を逐次表示する。

**注意**: 現行の `QueryService.ask()` は非ストリーミング（`invoke` で一括取得）のため、チャンクを逐次 yield する `ask_stream()` の追加実装が必要。unmask はマスクトークンがチャンク境界で分断される可能性があるため、表示は逐次・最終確定文のみ unmask する方式とする。

```python
with st.chat_message("assistant"):
    response_placeholder = st.empty()
    full_response = ""
    for chunk in query_service.ask_stream(question):
        full_response += chunk
        response_placeholder.markdown(full_response + "▌")
    response_placeholder.markdown(full_response)
```

### 5.3 ファイルアップロード登録（.eml / PDF）

`st.file_uploader` で受け取り、一時ファイルに保存して既存の登録経路（D-002/D-003で実装済み）を呼び出す。

```python
# PDFはマニュアル専用コレクションに登録（D-003の register --pdf と同一経路）
pdf_file = st.sidebar.file_uploader("PDFマニュアル", type=["pdf"])
if pdf_file:
    pages = PdfReader().parse_file(saved_tmp_path)
    index = IndexService(masking_service, collection_name=config.COLLECTION_MANUALS)
    result = index.register_pages(pages, file_name=pdf_file.name)
```

※ LLMバックエンド切替（ローカル/クラウド）のUIは [D-006](06-update-llm-switch.md) に分離した。

### 5.4 参照元表示

検索結果を expander で表示する。`AnswerResult.source_documents` は `{"content": str, "metadata": dict}` のリスト（Document オブジェクトではない）。メール（📧 件名+日付）とPDF（📄 ファイル名+ページ）で表示を分岐する。

```python
# src/main.py の _format_source と同一ロジック。
# CUI/GUI で重複しないよう共通モジュール（例: src/rag/formatting.py）への切り出しを実装時に行う
with st.expander("📎 参照元ドキュメント"):
    for doc in source_documents:
        st.markdown(f"- {format_source(doc['metadata'])}")
        st.text(doc["content"])
```

## 6. ディレクトリ差分

```
src/
├── app/
│   ├── __init__.py          # 新規
│   ├── main.py              # 新規: Streamlit メインページ
│   ├── components/
│   │   ├── __init__.py      # 新規
│   │   ├── chat.py          # 新規: チャットUI部品
│   │   ├── sidebar.py       # 新規: サイドバー部品（.eml/PDF/テキスト登録・件数表示）
│   │   └── masking_preview.py # 新規: マスキング確認部品
│   └── styles/
│       └── custom.css       # 新規: カスタムCSS（任意）
├── rag/
│   ├── query_service.py     # 更新: ask_stream()（ストリーミング回答）を追加
│   └── formatting.py        # 新規: 参照元表示の整形（main.py の _format_source を移設）
├── main.py                  # 更新: _format_source を rag/formatting.py へ移設（CUIモードは従来通り維持）
└── config.py                # 変更なし（LLM_BACKEND 切替は D-006 で対応）
```

## 7. 追加依存パッケージ

```toml
dependencies = [
    # ... 既存 ...
    "streamlit>=1.38",
]
```

## 8. 起動方法

```bash
# Webアプリ起動（ホスト直接）
streamlit run src/app/main.py

# Webアプリ起動（Docker。デフォルトCMDのため up だけで起動する）
docker compose up -d
# → http://localhost:8501

# CUIモード（従来通り）
python -m src.main ask "質問"
python -m src.main chat
docker compose exec -it app python -m src.main chat  # Docker内CUI
```

**Docker構成（2026-07-08 追記）**: WebUI対応のため Dockerfile のデフォルトCMDを `streamlit run`（0.0.0.0:8501, headless）に変更し、compose.yaml に `ports: 8501:8501` を追加。ボリュームは `./data:/app/data` に拡大（chroma_db 永続化＋CLI登録用入力ファイルの受け渡し）。

## 9. 制約・注意点

- LLM推論中は当該セッションの操作がブロックされる（ローカルLLM利用時は1〜2分。ストリーミング表示により生成中の進捗は視認できる）
- `st.session_state` の会話履歴はブラウザリロードで消失する
- 同時アクセスは想定しない（社内ツールのため単一ユーザー前提）
- LLMは当面ローカル（Ollama）固定。クラウド切替は [D-006](06-update-llm-switch.md) で対応する
- アップロードされたPDF/.emlの一時ファイルはPIIを含むため、登録処理後に必ず削除する（`data/` 外に残さない）
