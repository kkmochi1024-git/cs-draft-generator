# タスクリスト

## タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**
未完了タスク `[ ]` を残したまま作業を終了しない。

---

## フェーズ1: 依存パッケージ

- [x] pyproject.toml に `streamlit>=1.38` を追加
- [x] streamlit をインストールし import できることを確認（1.59.0 / AppTest 利用可）

## フェーズ2: バックエンド準備

- [x] src/rag/formatting.py を新規作成（`format_source(meta) -> str`）
- [x] src/main.py の `_format_source` を formatting.format_source に置換（cmd_ask/cmd_chat 内で遅延import。mask コマンドの遅延ロード維持のため）
- [x] src/rag/query_service.py に `ask_stream()` と `StreamingAnswer` を追加
  - [x] 検索・質問マスキングを同期実行、source_documents/mapping を確定
  - [x] LLM.stream でマスク済みチャンクを逐次 yield
  - [x] 検索0件時は is_empty=True + guidance
  - [x] ask() との共通処理を _build_prompt / _wrap_connection_error に抽出

## フェーズ3: Streamlit UI

- [x] src/app/__init__.py, src/app/components/__init__.py
- [x] src/app/components/sidebar.py（.eml/PDF/テキスト登録・件数表示・一時ファイル削除・登録ロジックは純粋関数化）
- [x] src/app/components/masking_preview.py（render_masking_result）
- [x] src/app/components/chat.py（会話履歴・ストリーミング表示・参照元）
- [x] src/app/main.py（ページ組み立て・session_state・cache_resource・sys.path bootstrap）

## フェーズ4: テスト

- [x] tests/test_formatting.py（format_source の分岐 7件）
- [x] tests/test_rag.py に ask_stream テスト追加（逐次yield・最終unmask・is_empty の3件）

## フェーズ5: 品質チェックと修正

- [x] pytest tests/ が全てパス（63 passed）
- [x] ruff check src/ tests/ がパス（All checks passed）
- [x] `streamlit run src/app/main.py` の起動スモーク
  - [x] AppTest でスクリプト実行（例外なし・タイトル/サイドバー/chat_input/コレクション別件数レンダリング確認）
  - [x] 実サーバー起動で HTTP 200 確認（headless・port 8599・確認後停止）

## フェーズ6: ドキュメント更新

- [x] settings/INDEX.md の D-004 ステータスを「実装済み」に更新
- [x] settings/04-update-web-ui.md のステータス更新（実装済み・実装日 2026-07-08）
- [x] /log-app-change を実行（docs/changelog/2026-07-08.md 4件目）
- [x] 実装後の振り返り（このファイルの下部に記録）

---

## 実装後の振り返り

### 実装完了日
2026-07-08

### 計画と実績の差分

**計画と異なった点**:
- `format_source` の main.py への import は、トップレベルではなく cmd_ask/cmd_chat 内の遅延importにした。`src/rag/__init__.py` が IndexService/QueryService を eager import しており、トップレベル import だと `mask` コマンドでも langchain/Chroma がロードされ、既存の遅延ロード設計（Ollama不要コマンドの軽量起動）が壊れるため。
- マスキング確認モーダル（設計書 §3.2）は独立コンポーネントの st.dialog ではなく、sidebar.py 内の `_confirm_text_registration`（@st.dialog）＋表示部品 `masking_preview.render_masking_result` の分担にした。ダイアログはトリガー元（テキスト登録ボタン）と同居させた方が状態管理が単純なため。
- 起動スモークは実サーバー起動に加えて Streamlit AppTest を使用。AppTest はスクリプト全体を実行して例外・レンダリング結果を検証できるため、HTTP 200 確認より強い保証が得られた。
- セッション途中でCLI制限による中断が発生したが、tasklist.md ベースの進捗管理により再開時に「フェーズ4実装済み・未記録」を正確に検出して継続できた。

**新たに必要になったタスク**:
- `src/app/main.py` に sys.path bootstrap を追加（`streamlit run` はスクリプトのディレクトリを sys.path に置くため、プロジェクトルートを明示追加しないと `src` パッケージが import できない）。
- サイドバー登録ロジックの純粋関数化（register_pdf_bytes / register_eml_bytes / register_text / get_collection_counts）。Streamlit UI から分離してテスト可能にした。

### 学んだこと

**技術的な学び**:
- Streamlit の AppTest（streamlit.testing.v1）は GiNZA のような重い初期化を含むアプリでも default_timeout を延ばせば実行でき、CI 向きの起動スモークとして有効。
- ストリーミング + PII unmask の両立は「逐次表示はマスク済み、確定時に一括 unmask」方式が単純で安全（マスクトークンのチャンク境界分断を組み立て直す必要がない）。
- `st.cache_resource` で MaskingService/QueryService をキャッシュすることで、rerun ごとの GiNZA 再ロードを回避できる。
- Chroma の count()（get_stats）は Ollama 接続不要のため、登録件数表示はオフラインでも動作する。

### 次回への改善提案
- Ollama 接続環境での E2E 確認（質問→ストリーミング回答→参照元表示、.eml/PDF アップロード登録）を実施する。D-003 の未検証事項と合わせて一度に確認するのが効率的。
- sidebar の登録純粋関数（register_*_bytes）のユニットテスト（IndexService モック＋一時ファイル削除の検証）は今回未追加。次回フェーズで追加を検討。
- 会話履歴の永続化・複数セッション対応が要件化したら D-004 スコープ外リスト（React移行基準含む）を再評価する。
