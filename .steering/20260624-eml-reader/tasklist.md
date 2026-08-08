# タスクリスト

## タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

---

## フェーズ1: .emlパーサー

- [x] src/etl/__init__.py を作成
- [x] src/etl/eml_reader.py を作成（ParsedEmail, EmailThread, EmlReader）
- [x] tests/fixtures/ にテスト用.emlファイルを作成（inquiry.eml, response.eml, standalone.eml）
- [x] tests/test_eml_reader.py を作成（9テスト全パス）

## フェーズ2: 設定・CLI拡張

- [x] src/config.py に SUPPORT_DOMAIN を追加
- [x] src/main.py の register コマンドに --eml / --eml-dir / --support-domain を追加
- [x] pyproject.toml に beautifulsoup4 を追加

## フェーズ3: 品質チェック

- [x] pytest tests/ が全てパスすることを確認（41テスト全パス）
- [x] ruff check src/ でリントエラーがないことを確認

## フェーズ4: ドキュメント更新

- [x] 実装後の振り返り（このファイルの下部に記録）

---

## 実装後の振り返り

### 実装完了日
2026-06-24

### 計画と実績の差分

**計画と異なった点**:
- レビューで `_find_thread_root` の循環参照リスクが指摘され、visited セットによるガードを追加
- ペア登録時のメタデータに subject/date が欠落しており、スレッドの最初のメールの情報を代表値として追加
- `hasattr(args, "eml")` が冗長であることが指摘され、argparseの仕様に基づき単純な `args.eml` チェックに修正

**新たに必要になったタスク**:
- ruff format の適用（format不一致が1箇所）

### 学んだこと

**技術的な学び**:
- Python標準ライブラリの `email` モジュールは `email.message_from_binary_file()` + `email.policy.default` の組み合わせがエンコーディング処理に最も安全
- GiNZAの地名ラベル問題（Location→Province/City/Country）はプロトタイプで修正済みだが、設計書とコードの乖離は早期に検出すべき
- 外部入力（emlファイル）を扱う場合、循環参照や不正データへの耐性を必ず考慮する

### 次回への改善提案
- HTMLメール・ISO-2022-JPエンコーディングのテストを追加する（カバレッジ向上）
- CLI統合テスト（IndexServiceモックでの--eml/--eml-dir実行テスト）を追加する
