# Docker イメージの再ビルド手順

## 概要

`src/` と `tests/` は `Dockerfile` の `COPY` でイメージに焼き込まれ、コンテナにはマウントされない（マウントされるのは `data/` のみ）。**ホストでコードを変更しても、再ビルドしない限りコンテナ（WebUI・CLI・コンテナ内の pytest）は古いコードのまま動く。**

2026-09-15 には、7/15 に修正済みのマスキングバグがイメージ未更新のため2か月間コンテナに反映されず、破損したデータが残っていた。

## 再ビルドが必要なとき

| 変更したもの | 再ビルド |
|---|---|
| `src/` 配下（アプリのコード） | 必要 |
| `tests/` 配下（コンテナ内で pytest を実行する場合） | 必要 |
| `pyproject.toml`（依存パッケージ） | 必要 |
| `Dockerfile` | 必要 |
| `.env` | 不要（`docker compose up -d` でコンテナを作り直せば反映） |
| `data/` 配下 | 不要（マウントされている） |
| `docs/`・`settings/`・`scripts/` | 不要（イメージに含まれない） |

## 手順

```bash
# 1. 再ビルド（pipefail を付けてビルド失敗を見逃さない）
set -o pipefail
docker compose build app 2>&1 | tail -20; echo "BUILD_EXIT=$?"

# 2. 新しいイメージでコンテナを作り直す
docker compose up -d

# 3. 反映を確認する（下記「確認方法」）

# 4. コンテナ内でテスト
docker compose exec app pytest tests/
```

## 確認方法

コンテナが新しいイメージで動いているかを確認する。

```bash
# コンテナのイメージIDと最新イメージのIDが一致すること
docker inspect cs-draft-generator-app-1 --format '{{.Image}}'
docker image inspect cs-draft-generator-app --format '{{.Id}} {{.Created}}'
```

変更した箇所がコンテナ内のコードに入っているかは、変更した行を grep して確かめるのが確実。

```bash
docker compose exec app grep -n "<変更した行の一部>" src/<変更したファイル>
```

## 注意事項

- **`docker compose build ... | tail` だけではビルドの失敗に気づけない。** パイプの終了コードは `tail` のものになるため、失敗しても終了コード 0 になる。`set -o pipefail` を付けるか、出力の末尾に `Built` があることを確認する
- **Rancher Desktop の再起動中などに `failed to connect to the docker API at unix:///var/run/docker.sock` が出ることがある。** ビルドは行われていないので、`docker context show` が `rancher-desktop` になっていることを確認してから再実行する
- `scripts/` もイメージに含まれない。`scripts/inspect_db.py` をコンテナで実行する場合は標準入力で渡す：
  ```bash
  docker compose exec -T app python - --db-path /app/data/chroma_db list < scripts/inspect_db.py
  ```
