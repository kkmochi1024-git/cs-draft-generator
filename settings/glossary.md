# 用語集

## ドメイン用語

| 用語 | 定義 | 使用例 | 関連用語 |
|---|---|---|---|
| 問い合わせ | 顧客からサポートチームへの質問・要望・報告 | 「新規問い合わせをRAGに登録する」 | チケット |
| 回答 | サポート担当者が顧客に送信する返信メール。回答ドラフトを確認・編集したもの | 「回答ドラフトを確認し、回答として送信する」 | 回答ドラフト |
| 回答ドラフト | AIが生成した回答の下書き。担当者が確認・編集してから送信する。本システムは回答ドラフトの生成までを担い、送信は人間が行う | 「回答ドラフトの採用率を測定する」 | 回答 |
| チケット | Zendeskにおける問い合わせの管理単位。問い合わせ内容とそのやり取りを含む | 「チケットのステータスがsolvedに変更された」 | 問い合わせ |
| サポートドメイン | サポート担当者のメールドメイン。eml_readerモジュールで問い合わせ/回答のペア判定に使用 | 「@example.com をサポートドメインとして設定する」 | - |

## 技術用語

### AI / ML 関連

| 用語 | 定義 | 使用例 | 関連用語 |
|---|---|---|---|
| PII | Personally Identifiable Information（個人識別情報）。氏名、メールアドレス、電話番号、住所等 | 「PIIをマスキングしてからLLMに渡す」 | マスキング |
| マスキング | テキスト内のPIIをマスクトークン（[PERSON_1]等）に置換すること | 「正規表現とNERの2層でマスキングを行う」 | PII, アンマスク, マスクトークン |
| アンマスク | マスクトークンを元のPII値に復元すること | 「回答生成後にアンマスクして顧客名を復元する」 | マスキング, マスクトークン |
| マスクトークン | PIIの置換先となるトークン文字列。`[PERSON_1]`、`[EMAIL_1]` 等の形式 | 「マスクトークンをマッピングテーブルで管理する」 | マスキング |
| RAG | Retrieval-Augmented Generation。外部データを検索してLLMの回答生成を補強する手法 | 「RAGで過去メールを参照して回答を生成する」 | Embedding, Vector DB |
| Embedding | テキストをベクトル（数値配列）に変換したもの。意味的な類似度計算に使用 | 「nomic-embed-textでEmbeddingを生成する」 | RAG, チャンク |
| NER | Named Entity Recognition（固有表現認識）。テキストから人名・地名等の固有表現を検出する技術 | 「GiNZA NERで人名と住所を検出する」 | GiNZA, spaCy |
| チャンク | テキストを一定サイズに分割した断片。Embedding生成とVector DB登録の単位。本プロジェクトでは512トークン、オーバーラップ50トークン | 「512トークンごとにチャンク分割する」 | Embedding |
| LLMバックエンド | 回答生成に使用するLLMの実行環境。ローカル（Ollama）またはクラウド（Claude API） | 「LLMバックエンドをローカルからクラウドに切り替える」 | Ollama, Claude API |

### データ関連

| 用語 | 定義 | 使用例 | 関連用語 |
|---|---|---|---|
| Vector DB | ベクトルデータを格納・検索するデータベース | 「マスキング済みテキストをVector DBに登録する」 | Embedding, ChromaDB |
| ChromaDB | 本プロジェクトで使用するVector DB。Pythonネイティブで軽量。`support_emails` と `product_manuals` の2コレクションで構成 | 「ChromaDBに過去メールを登録する」 | Vector DB |
| コレクション | ChromaDBにおけるデータの格納単位。本プロジェクトでは `support_emails`（過去メール）と `product_manuals`（製品マニュアル）の2つ | 「両コレクションを横断検索して上位5件を取得する」 | ChromaDB |

### ツール・フレームワーク

| 用語 | 定義 | 使用例 | 関連用語 |
|---|---|---|---|
| Ollama | ローカルLLMの実行基盤。HTTPサーバーとして動作し、ホストOS上で稼働する | 「Ollamaでgemma4:12bモデルを実行する」 | LLMバックエンド |
| Claude API | Anthropic社のクラウドLLMサービス。マスキング済みテキストのみ送信する | 「マスキング精度検証後にClaude APIに切り替える」 | LLMバックエンド |
| GiNZA | 日本語NLPライブラリ。spaCy上で動作し、日本語の固有表現認識（NER）を提供する | 「GiNZA NERで人名と住所を検出する」 | spaCy, NER |
| spaCy | オープンソースのNLPライブラリ。GiNZAの基盤として使用 | 「spaCyのパイプラインでNER処理を実行する」 | GiNZA |
| LangChain | RAGフレームワーク。Ollama/Claude API両対応で、検索→プロンプト構築→LLM呼び出しのチェーンを構築する | 「LangChainでRAGチェーンを構築する」 | RAG |
| Streamlit | PythonのWebアプリフレームワーク。チャットUI（`st.chat_message`）を標準搭載。第3弾アップデートで使用 | 「StreamlitでチャットUIを構築する」 | WebアプリUI |
| PyMuPDF | PDFテキスト抽出ライブラリ。ページ単位でテキストを取得する。第2弾アップデートで使用 | 「PyMuPDFでマニュアルPDFからテキストを抽出する」 | - |

## 略語一覧

| 略語 | 正式名称 | 参照 |
|---|---|---|
| PII | Personally Identifiable Information | → 技術用語 AI/ML関連 |
| PRD | Product Requirements Document | プロダクト要求定義書 |
| RAG | Retrieval-Augmented Generation | → 技術用語 AI/ML関連 |
| NER | Named Entity Recognition | → 技術用語 AI/ML関連 |
| ETL | Extract, Transform, Load | データの抽出・変換・格納 |
| CLI | Command Line Interface | コマンドラインインターフェース |
| GUI | Graphical User Interface | グラフィカルユーザーインターフェース |
| MVP | Minimum Viable Product | 実用最小限の製品 |
| KPI | Key Performance Indicator | 重要業績評価指標 |
| API | Application Programming Interface | アプリケーションプログラミングインターフェース |
