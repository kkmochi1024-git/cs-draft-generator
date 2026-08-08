# 設計書（詳細設計書作成の作業設計）

## 成果物の配置と位置づけ

- 新規フォルダ: `settings/detailed-design/`（README + モジュール別5ファイル）
- フェーズ別の差分設計書（phases/）とは異なり、**現時点の実装全体のスナップショット**を記述する
- **settings/ 直下の新フォルダとする理由**（2026-07-15 ユーザー決定）: phases/ は各フェーズの凍結された差分履歴、本設計書は実装の進行に合わせて更新し続ける現状スナップショットでライフサイクルが異なる。phases/ の90番台規則（`{番号}-{概要}.md` の単一ファイル想定）はフォルダ構成に合わず、settings/ 直下の方が新規参画者に発見されやすい
- 対象コード: `src/` 配下全体（約2,100行、フェーズ4＝D-004 WebUI まで実装済みの状態）
- **モジュール別分割とする理由**（2026-07-15 ユーザー決定）: 単一ファイルだと800〜1,200行級となり読みにくい。分割軸を「フェーズ」でなく「モジュール」にするのは、①フェーズ軸は既存 phases/01〜04 と重複する、②1モジュールの記述が複数ファイルに散る、③コードのパッケージ構造と1対1対応させると保守時に「変更したモジュールの設計書だけ更新」で済むため。モジュール間の繋がりは README の全体構成図・シーケンス図で担保する
- 各モジュールファイルは150〜300行程度を目安とする

## 実行体制（モデル使い分けポリシー準拠）

| 工程 | 担当 | 理由 |
|---|---|---|
| 骨子設計・記載ルール策定 | メイン会話（Fable） | 設計判断を伴うため（本 design.md で確定済み） |
| 詳細設計書の初版執筆 | worker サブエージェント | 全ソース約20ファイルの読解＋長文執筆＝大量 Read を伴う機械的作業。骨子・記載ルールは本書で確定済みのため実行者の設計判断は不要 |
| コードとの整合性検証・レビュー・修正 | メイン会話（Fable） | 検証・受け入れは計画側モデルが行う |

## 詳細設計書のファイル構成と骨子（worker はこの骨子に忠実に従うこと）

フォルダ: `settings/detailed-design/`

### README.md（全体像・モジュール間の繋がり担当）

```markdown
# 詳細設計書（現行実装スナップショット）

## 1. 本書の位置づけ
- 対象: D-001（プロトタイプ）〜 D-004（WebUI）実装済みの現行コード
- 対象外: D-005（Zendesk連携）・D-006（LLM切替）※未実装。ただし config.py 等に
  既に存在する切替用設定があれば「実装済みの範囲」として記載する
- 読み方: 各フェーズの経緯は phases/01〜04、要求は PRD を参照。本書は「現在どう動くか」のみ
- ファイル一覧表（各モジュールファイルへの相対リンク＋1行概要）

## 2. 全体構成
- 2.1 モジュール構成図（Mermaid graph: main.py / app/ → rag/ → masking/、etl/ の依存方向）
- 2.2 パッケージ一覧表（パッケージ / 責務 / 主要公開シンボル / 依存先 / 詳細ファイルへのリンク）
- 2.3 実行形態（CLI: python -m src.main、WebUI: streamlit run src/app/main.py、Docker構成）

## 3. 主要ユースケースのシーケンス図（Mermaid sequenceDiagram 必須）
- 3.1 データ登録（WebUI で PDF をアップロードした場合: sidebar → PdfReader → MaskingService
  → IndexService → ChromaDB）
- 3.2 回答生成（WebUI チャット: chat → MaskingService.mask → QueryService.ask_stream
  → ChromaDB検索 → Ollama → unmask → 画面表示）
- 3.3 回答生成（CLI ask/chat の場合の差分を短く補足）

## 4. テスト構成
- tests/ 配下の各テストファイルと対象モジュールの対応表、fixtures の概要
```

### 01-masking.md（src/masking/）

```markdown
## 1. データモデル（models.py: Entity, MaskingResult の全フィールドと意味）
## 2. RegexMasker（regex_masker.py: 検出パターンの一覧表〈PII種別 / 正規表現の概要 / マスクトークン形式〉）
## 3. NerMasker（ner_masker.py: GiNZA 利用方法、検出対象エンティティラベル、モデル未ロード時のフォールバック）
## 4. MaskingService（service.py: mask() の処理フロー〈正規表現→NER の2層、トークン採番、マッピング生成〉、
   unmask()、_apply_entities / _map_ner_to_original の役割。mask() は Mermaid フローチャート必須）
```

### 02-rag.md（src/rag/）

```markdown
## 1. データモデル（models.py: RegisterResult, AnswerResult, StreamingAnswer）
## 2. IndexService（index_service.py: register() / register_pages() の処理フロー、チャンク分割設定、
   コレクション構成〈support_emails / product_manuals〉、メタデータ設計、
   _orig_to_masked_pos / _page_range_str によるページ位置マッピングの仕組み、get_stats()）
## 3. QueryService（query_service.py: ask() / ask_stream() の処理フロー、_search() の横断検索と件数、
   _build_prompt() のプロンプト構造、_wrap_connection_error() のエラーハンドリング）
## 4. formatting.py（format_source() の出典表示ルール）
```

### 03-etl.md（src/etl/）

```markdown
## 1. EmlReader（eml_reader.py: ParsedEmail / EmailThread モデル、parse_file / parse_directory、
   detect_threads のスレッド検出ロジック、_detect_pairs の問い合わせ/回答ペア抽出、
   HTML→テキスト変換、エンコーディング失敗時のスキップ動作）
## 2. PdfReader（pdf_reader.py: ExtractedPage モデル、parse_file / parse_directory、
   _clean_text の整形ルール、抽出失敗時のスキップ動作）
```

### 04-cli.md（src/main.py・src/config.py）

```markdown
## 1. 設定管理（config.py: 定数名 / 環境変数名 / デフォルト値 / 用途 / 参照元モジュール の一覧表）
## 2. コマンド体系表（mask / register / ask / chat、各オプション）
## 3. 各コマンドの処理フロー（cmd_register はテキスト・.eml（ファイル/ディレクトリ）・PDF（ファイル/
   ディレクトリ）の分岐を含むため Mermaid フローチャート必須。他は箇条書きで可）
```

### 05-webui.md（src/app/）

```markdown
## 1. 画面構成（main.py のページ構成、st.session_state で保持する状態の一覧表）
## 2. サイドバー（sidebar.py: PDF/.eml/テキスト登録の各フロー、テキスト登録時の
   マスキング確認ステップ、コレクション件数表示）
## 3. チャット（chat.py: _generate_answer のストリーミング表示・アンマスク・出典表示の流れ）
## 4. マスキングプレビュー（masking_preview.py）
```

## 記載ルール（worker 必読）

1. **必ず実コードを読んでから書く**。architecture.md 等の既存ドキュメントからの転記で済ませない（既存ドキュメントは「あるべき姿」を含み、実装と乖離している可能性がある。乖離を見つけたら設計書には**実装どおり**に書き、乖離点を作業報告に含める）
2. 公開クラス・公開関数は**全て**記載する。プライベート関数（`_` 始まり）は処理の流れの理解に必要なもののみ記載する
3. 各関数の記述粒度: 「責務 / 入力 / 出力 / 処理の要点（箇条書き2〜5行）」。コードの逐行翻訳はしない
4. 具体値（チャンクサイズ・検索件数・コレクション名・マスクトークン形式・モデル名等）は**コードから読み取った実値**を記載する
5. Mermaid 図は上記骨子で「必須」と明記した箇所（4.4 mask()、7.2 cmd_register、9章）には必ず入れる。その他もテキストで流れが追いにくい箇所には追加してよい
6. ファイルパス・行数参照は書かない（コード変更ですぐ陳腐化するため）。ファイル名とシンボル名で参照する
7. 文体・用語は settings/glossary.md と既存設計書に合わせる（です・ます調は使わず、体言止め・である調）
8. 各ファイルの冒頭に「最終更新: 2026-07-15 / 対象: D-001〜D-004 実装時点 / 対象コード: src/xxx/」を明記する
9. **ファイル間リンク**: README には各モジュールファイルへの相対リンクを置き、各モジュールファイルの冒頭には README への戻りリンクを置く。他モジュールに言及する際は該当ファイルへ相対リンクする（例: `[01-masking.md](01-masking.md)`）
10. 各モジュールファイルは150〜300行程度を目安とする。超過しそうな場合は記述粒度（ルール3）を守れているか見直す

## データフロー（この作業自体の流れ）

```
1. worker へ委譲（本 design.md + requirements.md を委譲プロンプトで指定）
2. worker: src/ 全ファイル + tests/ 一覧 + glossary.md を読み、
   settings/detailed-design/ 配下の6ファイル（README + モジュール別5ファイル）の初版を執筆
3. メイン会話: 初版を全ソースと突き合わせて整合性検証（誤記・欠落・実装との乖離、
   ファイル間リンクの整合）
4. /review-doc で採点レビュー（settings/ 配下のため doc-reviewer 採点方式）
5. 指摘修正 → INDEX.md 更新（リンク先は README.md）＋ repository-structure.md の
   ツリーに detailed-design/ を追記 → /log-app-change
```

## エラーハンドリング戦略（作業上のリスク対応)

- worker の成果物に実装との乖離があった場合: メイン会話の検証工程で検出し、メイン会話が直接修正する（軽微な場合）。乖離が広範な場合は該当章を worker に差し戻す
- 検証で「既存マスター仕様書と実装の乖離」を発見した場合: 本作業では詳細設計書に実装どおり記載し、マスター仕様書の改訂は**別作業として報告のみ**行う（スコープ外のため）

## テスト戦略

- コード変更を伴わないため自動テストは実施しない
- 品質担保は「メイン会話によるコード突き合わせ検証」＋「/review-doc 採点レビュー」の2段構え

## セキュリティ考慮事項

- 詳細設計書に PII の実例・APIキー・実データのサンプルを記載しない（マスクトークン形式の説明には架空の例を使う）
