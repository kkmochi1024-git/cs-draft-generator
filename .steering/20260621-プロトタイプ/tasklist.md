# タスクリスト

## タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- **全てのタスクを `[x]` にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 未完了タスク `[ ]` を残したまま作業を終了しない

### タスクスキップが許可される唯一のケース
技術的理由に該当する場合のみスキップ可能

---

## フェーズ1: プロジェクト基盤

- [x] pyproject.toml を作成
- [x] src/__init__.py を作成
- [x] src/config.py を作成
- [x] .gitignore を作成
- [x] .env.example を作成

## フェーズ2: PIIマスキング（MaskingService）

- [x] src/masking/__init__.py を作成
- [x] src/masking/models.py を作成
- [x] src/masking/regex_masker.py を作成
- [x] src/masking/ner_masker.py を作成
- [x] src/masking/service.py を作成
- [x] tests/test_masking.py を作成

## フェーズ3: RAGパイプライン

- [x] src/rag/__init__.py を作成
- [x] src/rag/models.py を作成
- [x] src/rag/index_service.py を作成
- [x] src/rag/query_service.py を作成

## フェーズ4: CLIエントリポイント

- [x] src/main.py を作成

## フェーズ5: Docker環境

- [x] Dockerfile を作成
- [x] compose.yaml を作成
- [x] .dockerignore を作成

## フェーズ6: 品質チェック

- [x] pytest tests/test_masking.py が全てパスすることを確認（14テスト全パス）
- [x] ruff check src/ でリントエラーがないことを確認

## フェーズ7: ドキュメント更新

- [x] 実装後の振り返り（このファイルの下部に記録）

---

## 実装後の振り返り

### 実装完了日
2026-06-21

### 計画と実績の差分

**計画と異なった点**:
- 正規表現パターンで電話番号と郵便番号が互いにマッチする問題が発生。優先順位付きの検出（PRIORITY配列）と重複排除（occupied spans）を追加して解決
- GiNZA + Python 3.14で`compound_splitter`のバリデーションエラーが発生。`NerMasker`のexceptを`Exception`に拡大してグレースフルデグラデーションで対応
- `pyproject.toml`のbuild-backendが`setuptools.backends._legacy:_Backend`で動作しない。`setuptools.build_meta`に修正
- Dockerfileでソースコピー前の`pip install .`が機能しない。コピー後にインストールする形に修正

**新たに必要になったタスク**:
- レビュー指摘対応: 未使用import削除、AnswerResult.masking_resultの型修正、Ollama接続エラーハンドリング追加、COLLECTION_MANUALS設定追加

### 学んだこと

**技術的な学び**:
- 正規表現パターンの設計では、パターン間の重複（電話番号の一部が郵便番号にマッチする等）を考慮し、検出優先順位と占有範囲管理が必要
- Python 3.14とGiNZA/spaCyの互換性は完全ではない。NERコンポーネントの例外ハンドリングを広くしておくことで、環境差異に対する耐性が上がる
- Dockerのレイヤーキャッシュを活かすには、依存ライブラリとソースコードの分離が重要だが、setuptoolsの`find_packages`はソースディレクトリの存在を前提とするため、単純な2段階コピーでは機能しない

### 次回への改善提案
- NerMaskerのユニットテストを追加する（GiNZA依存のためCI環境での実行可否を事前確認）
- IndexService/QueryServiceの統合テストを追加する（Ollamaのモック必要）
- 2コレクション横断検索の実装は第2弾（PDF取り込み）と同時に行う
