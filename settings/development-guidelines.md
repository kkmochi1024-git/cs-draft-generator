# 開発ガイドライン

## コーディング規約

### Python

- **バージョン**: 3.11+
- **インデント**: スペース4つ
- **命名規則**:
  - 変数・関数: `snake_case`
  - クラス: `PascalCase`
  - 定数: `UPPER_SNAKE_CASE`
  - ファイル名: `snake_case.py`
- **フォーマッター**: `ruff format`
- **リンター**: `ruff check`
- **型ヒント**: 全ての公開関数に型ヒントを付ける

### コメント規約

- コメントはデフォルトで書かない
- WHYが非自明な場合のみ1行コメントを付ける
- docstringは公開APIのみ、1行で記述

### クロスプラットフォーム実装規約

macOS / Windows / Linux での動作を保証するため、以下を守る：

- ファイルパスは `pathlib.Path` を一貫使用し、`/` や `\` のハードコードを禁止する
- 改行コードの差異（CRLF / LF）はテキスト処理側で吸収する

## Git運用ルール

### ブランチ戦略

```
main ─── 安定版（直接コミット可、小規模プロジェクトのため）
  │
  └── feature/* ─── 機能開発（大きな変更時のみ使用）
  └── fix/* ─── バグ修正（大きな変更時のみ使用）
```

個人開発・小規模プロジェクトのため、mainへの直接コミットを基本とする。以下に該当する「大きな変更」の場合のみfeatureブランチを使用する：
- 3ファイル以上の変更を伴う機能追加
- 新規コンポーネント（サービスクラス・ETLモジュール等）の追加
- データモデルの変更（ChromaDBコレクション構成の変更等）
- 既存インターフェースの破壊的変更

### コミットメッセージ規約

```
{type}: {subject}
```

| type | 用途 |
|---|---|
| feat | 新機能追加 |
| fix | バグ修正 |
| docs | ドキュメント変更 |
| refactor | リファクタリング |
| test | テスト追加・修正 |
| chore | ビルド・設定変更 |

### Git管理外ファイル

`.gitignore` に含める：
- `.env`（秘匿情報）
- `data/`（ChromaDBデータ）
- `.steering/ignore/`（機能と無関係な作業のステアリングファイル。機能開発のステアリングは `.steering/` 直下に置きGit管理対象）
- `__pycache__/`, `.venv/`

## テスト方針

### テスト種類と対象

| テスト種類 | 対象 | カバレッジ目標 |
|---|---|---|
| ユニットテスト | MaskingService（各PIIパターン） | 90%以上 |
| ユニットテスト | RegexMasker / NerMasker | 90%以上 |
| 統合テスト | 登録→検索→回答の一連のフロー | 主要パスをカバー |
| 統合テスト | .eml / PDF読み取り→登録 | 主要パスをカバー |

### テスト実行コマンド

```bash
# Docker環境（推奨）
docker compose exec app pytest tests/
docker compose exec app pytest tests/test_masking.py -v
docker compose exec app pytest tests/ --cov=src --cov-report=term-missing

# ホスト直接実行（開発時）
pytest tests/
pytest tests/test_masking.py -v
pytest tests/ --cov=src --cov-report=term-missing
```

### テストデータ

- テスト用サンプルは `tests/fixtures/` に配置
- PIIを含む生データはテストに使用しない（ダミーデータを使用）

## レビュー基準

### PRレビューチェックリスト（大きな変更時のみ）

- [ ] コーディング規約に準拠しているか
- [ ] テストが追加・更新されているか
- [ ] PIIを含むデータがハードコードされていないか
- [ ] `.env` に新しい環境変数が追加された場合、`.env.example` も更新されているか

## 環境構築手順

### 前提条件

- Docker Desktop（macOS / Windows）または Docker Engine（Linux）
- Ollama がホストOSにインストール済み
- Python 3.11+（ホスト直接実行時のみ）

### Docker環境セットアップ

```bash
# Ollamaモデル取得
ollama pull gemma4:12b
ollama pull nomic-embed-text

# 環境変数ファイル準備
cp .env.example .env

# ビルド・起動
docker compose build
docker compose up -d

# 動作確認
docker compose exec app python -m src.main mask "テスト太郎 test@example.com"
```

### ホスト直接実行（開発時）

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
python -m spacy download ja_ginza
```
