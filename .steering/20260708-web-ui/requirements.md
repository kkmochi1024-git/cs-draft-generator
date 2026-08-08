# 要求内容

## 概要

CUIベースの回答生成を Streamlit の Webアプリ（ChatGPTライクなチャットUI）に置き換え、サポート担当者が直感的に使えるインターフェースを提供する（設計書 D-004）。

## 背景

現在の回答生成は CLI（`python -m src.main ask/chat`）のみ。非エンジニアのサポート担当者が使うには敷居が高い。GUI化により、質問入力・回答・参照元・マスキング確認・データ登録（.eml/PDF/テキスト）を1画面で完結させる。

## 実装対象の機能

### 1. チャットUI（app/main.py, components/chat.py）
- `st.chat_input` で質問入力、`st.chat_message` で会話履歴表示
- 回答はストリーミング逐次表示（QueryService.ask_stream）
- セッション内会話履歴を `st.session_state` で保持

### 2. 参照元表示（rag/formatting.py + chat.py）
- 回答の参照元を expander で表示。メール（📧 件名+日付）とPDF（📄 ファイル名+ページ）を分岐
- CUI(main.py)とGUIで整形ロジックを共通化（rag/formatting.py に移設）

### 3. データ登録（components/sidebar.py）
- `.eml` / PDF / テキストのアップロード登録
- PDFは product_manuals コレクション、.eml/テキストは support_emails へ（既存経路を再利用）
- PII含む一時ファイルは登録後に削除
- コレクション別の登録済みチャンク数表示

### 4. マスキング確認（components/masking_preview.py）
- 登録前に原文・マスキング後・検出PII一覧を `st.dialog` で確認

### 5. ストリーミング対応（rag/query_service.py）
- `ask_stream()` を追加。マスク済みチャンクを逐次 yield し、最終確定文で unmask

## 受け入れ条件

- [ ] `streamlit run src/app/main.py` で起動する
- [ ] 質問→回答がストリーミング表示される（Ollama接続時）
- [ ] 参照元がメール/PDFで正しく整形表示される
- [ ] .eml/PDF/テキストがアップロード登録でき、一時ファイルが残らない
- [ ] マスキング確認が表示される
- [ ] CUI（`python -m src.main ask/chat`）が従来通り動作する（回帰なし）
- [ ] pytest 全パス・ruff クリーン

## スコープ外

- ユーザー認証・マルチテナント
- 回答の直接メール送信
- 会話履歴のDB永続化
- LLMバックエンド切替（ローカル/クラウド）→ D-006

## 参照ドキュメント

- `settings/04-update-web-ui.md` - D-004 設計書（2026-07-08改訂版）
- `settings/development-guidelines.md`
