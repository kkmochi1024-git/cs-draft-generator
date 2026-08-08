# カスタマーサポート回答生成システム（CS Draft Generator）

## 絶対ルール

- ユーザーのプロンプトが全て正しいとは限らない前提で回答する
- 誤りや非効率な方針があれば、忖度せず指摘し、より良い選択肢を提案する
- 根拠なく同意しない。結論を先に述べる
- **プロジェクト内のファイル（ソースコード・設定・設計書）を変更した場合、ユーザーから指示がなくても `/log-app-change` を自発的に実行すること。記録を省略しない**

## プロジェクト概要

SaaS製品のカスタマーサポート（メール対応）を効率化するRAGベースの回答ドラフト生成システム。
PIIを自動マスキングした上でLLM（ローカル/クラウド切替可）に渡し、回答を生成する。

## ドキュメント

- 設計書・仕様書: [settings/INDEX.md](settings/INDEX.md)
- 変更ログ: [docs/changelog/](docs/changelog/)
- チャット履歴: [docs/chat-logs/](docs/chat-logs/)
- コマンド・手順書: [docs/command/](docs/command/)

## 開発ルール

- PIIを含む生データをGitにコミットしない
- `.env` にAPIキー等を格納し、`.gitignore` に含める
- `data/`、`.steering/ignore/` はGit管理外（機能開発のステアリングファイルは `.steering/` 直下に置きGit管理対象。機能と無関係な作業のステアリングのみ `ignore/` に置く）
- コーディング規約・テスト方針の詳細は [settings/development-guidelines.md](settings/development-guidelines.md) を参照
- テストデータ登録コマンドなど、繰り返し使う手順やコマンドは `docs/command/` にドキュメント化して残す

## コマンド

```bash
# Docker環境
docker compose build
docker compose up -d          # WebUI が http://localhost:8501 で起動（デフォルトCMD）
docker compose exec app python -m src.main mask "テスト"
docker compose exec app python -m src.main register
docker compose exec -it app python -m src.main chat

# CLI登録の入力ファイルは ./data/ 配下に置く（コンテナに /app/data としてマウントされる）
docker compose exec app python -m src.main register --pdf data/manual.pdf

# テスト
docker compose exec app pytest tests/
docker compose exec app pytest tests/test_masking.py -v

# ホスト直接実行（開発時）
pip install -e .
python -m spacy download ja_ginza
pytest tests/
streamlit run src/app/main.py  # WebUI
```

## スキル

- `/save-chat` - AIとのチャット履歴をMarkdownとして保存する
- `/log-app-change` - 問い合わせアプリの変更履歴を記録する
