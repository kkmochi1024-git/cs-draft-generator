# 要求内容

## 概要

.emlファイルからメール本文を自動抽出し、マスキング→RAG登録する機能を追加する。

## 背景

プロトタイプではテキスト手動入力のみ対応。実運用では過去のメールを.emlファイルとしてエクスポートし、一括でRAGに取り込む必要がある。

## 実装対象の機能

### 1. .emlファイルパーサー（eml_reader.py）
- .emlファイルからヘッダー（件名、送信元、送信先、日時、Message-ID）と本文を抽出
- マルチパートメールのtext/plain優先抽出、text/htmlのテキスト化
- 文字エンコーディング自動検出（UTF-8, ISO-2022-JP, Shift_JIS）
- 引用部分の分離

### 2. スレッド検出
- In-Reply-To / References ヘッダーで同一スレッドのメールを紐付け
- サポートドメインで問い合わせ/回答のペアを判別

### 3. CLI拡張（main.py）
- `--eml path/to/file.eml` で単一ファイル登録
- `--eml-dir path/to/emails/` でディレクトリ一括登録
- `--support-domain example.com` でサポートドメイン指定

### 4. ChromaDBメタデータ拡張
- source="eml"、subject、date、thread_id、role（inquiry/response）を付与

### 5. config.py 拡張
- SUPPORT_DOMAIN 設定を追加

## 受け入れ条件

### .emlパーサー
- [ ] .emlファイルからメール本文を抽出できる
- [ ] 件名・送信元・日時をメタデータとして取得できる
- [ ] マルチパートメールのtext/plainを優先抽出できる
- [ ] 不正なエンコーディングのファイルはスキップしてログ出力する

### スレッド検出
- [ ] In-Reply-To / References でスレッドを構築できる
- [ ] サポートドメインで問い合わせ/回答を判別できる

### CLI
- [ ] `--eml` で単一ファイルを登録できる
- [ ] `--eml-dir` でディレクトリ内の全.emlを一括登録できる

### テスト
- [ ] eml_reader のユニットテストが全てパスする

## スコープ外

- .msg形式のサポート
- 添付ファイルの内容読み取り
- Outlook直接接続

## 参照ドキュメント

- `settings/02-update-eml-reader.md` - 第1弾設計書
- `settings/functional-design.md` - 機能設計書
