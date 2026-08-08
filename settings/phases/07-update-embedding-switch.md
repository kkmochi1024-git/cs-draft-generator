# D-007: 第6弾アップデート - Embedding切替（クラウド対応・再登録設計）

| 項目 | 値 |
|---|---|
| フェーズ | 第6弾アップデート |
| ステータス | レビュー |
| 作成日 | 2026-07-20 |
| 前提 | [D-006 生成LLMマルチプロバイダ切替](06-update-llm-switch.md) が実装済みであること（プロバイダ設定体系・`langchain-openai` 依存を流用） |
| 経緯 | D-006 のスコープ外だった Embedding のクラウド化をユーザー要望により計画化。**Embedding の変更は既存 ChromaDB の登録済みベクトルとの互換性を失わせ全再登録が必要になる**ため、実行時切替である D-006 とはリスクの性質が異なり、独立フェーズとした |

## 1. ゴール

Embedding モデルをローカル（Ollama / nomic-embed-text）とクラウド（Azure OpenAI / text-embedding-3 系）で切り替えられるようにする。
切替に伴うベクトル非互換を、**一時コレクションを用いた再登録**（再登録中も旧データで検索継続でき、失敗時も旧データが無傷）で安全に扱えるようにし、設定不整合（登録時と検索時で異なるEmbedding）を構造的に検出する。

> **用語定義**: 本設計で言う「コレクションの分離」とは、**1つのコレクション内に異なるEmbedding構成のベクトルを混在させないこと**を指す（同一コレクション名を維持したまま、再登録時のみ一時コレクションを経由して中身を入れ替える）。プロバイダごとに恒久的な別名コレクションを併存させるブルーグリーン方式は採らない（`QueryService` の参照コレクション名 `support_emails` / `product_manuals` を不変に保ち、現行コードへの影響を最小化するため）。

### スコープ内

- Embedding プロバイダの切替（環境変数 `EMBEDDING_PROVIDER`）
- Azure OpenAI Embedding 連携（`langchain-openai` の `AzureOpenAIEmbeddings`）
- Embedding とコレクションの整合性ガード（不一致検出）
- 再登録（reindex）コマンドの追加
- Embedding 入力（登録テキスト・検索クエリ）がマスキング済みであることの回帰テスト

### スコープ外

- 複数 Embedding の並行運用・自動同期（コレクション二重管理） → 将来検討。本フェーズは「切替＋再登録」まで
- 検索精度のチューニング（リランキング・ハイブリッド検索） → 将来検討
- コスト管理 → 将来検討
- WebUI からのランタイム切替 → **意図的に提供しない**（下記 2.4）

## 2. 設計方針（ドラフト）

### 2.1 設定体系

| 環境変数 | 値 | 説明 |
|---|---|---|
| `EMBEDDING_PROVIDER` | `ollama`（既定） / `azure_openai` | Embedding のプロバイダ |
| `EMBEDDING_MODEL` | 例: `nomic-embed-text`（ollama時） / `text-embedding-3-small`（azure時。実装時に確認） | モデル名（既存変数を流用） |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | — | Embedding 用デプロイメント名（生成用と別デプロイメント） |

Azure の認証系変数（`AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_VERSION`）は D-006 で導入済みのものを共用する。

### 2.2 Embedding ファクトリ

`IndexService` / `QueryService` 双方の `OllamaEmbeddings` 直接生成をやめ、ファクトリに置き換える（D-006 の `llm_factory` と同じ構造）。

D-006 の `llm_factory` と同様、未知プロバイダはサイレントフォールバックせず明確なエラーで止める（`ollama` も明示分岐にする）。

```python
# src/rag/embedding_factory.py（新規・案）
def create_embeddings(provider: str):
    if provider == "ollama":
        return OllamaEmbeddings(
            model=config.EMBEDDING_MODEL,
            base_url=config.OLLAMA_BASE_URL,
        )
    if provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_deployment=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            model=config.EMBEDDING_MODEL,  # トークナイザ・次元数推定のため明示的に渡す
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
    raise ValueError(
        f"未知の EMBEDDING_PROVIDER です: {provider!r}（有効値: ollama / azure_openai）"
    )
```

- `EMBEDDING_MODEL` は両プロバイダで使用する（Ollama はモデル名、Azure はデプロイメントの実モデル名）。**コレクション metadata に記録する `embedding_model` の値は、プロバイダによらず `EMBEDDING_MODEL` を採用する**（`AZURE_OPENAI_EMBEDDING_DEPLOYMENT` はインフラ上のデプロイメント名でモデル同一性の判定に使えないため、metadataのソースには使わない）
- `azure_openai` 選択時に必須環境変数（`AZURE_OPENAI_EMBEDDING_DEPLOYMENT` 等）が未設定の場合は、SDK由来の分かりにくいエラーに委ねず、ファクトリで**明確なエラーで停止**する（未知プロバイダと同じ設計原則）

### 2.3 ベクトル互換性の扱い（本フェーズの核心）

Embedding モデルが変わるとベクトル空間・次元数が変わる（例: nomic-embed-text は 768次元、text-embedding-3-small は 1536次元。実装時に確認）。登録時と検索時の Embedding が異なると、エラーになるか、より悪い場合**黙って無意味な検索結果を返す**。これを構造的に防ぐ。

1. **コレクション metadata に Embedding 構成を記録する**: 登録時に `embedding_provider` / `embedding_model` をコレクションの metadata に書き込む
2. **起動時ガード**: `IndexService` / `QueryService` の初期化時に、現在の設定とコレクション metadata を照合し、不一致なら**明確なエラーで停止**して再登録手順を案内する（黙ってフォールバックしない）
3. **metadata が無いコレクションの扱い（ドキュメント有無で分岐）**:
   - **1件以上のドキュメントがある** → 本フェーズ以前に登録された既存データとみなし、`embedding_provider=ollama`・`embedding_model=`（**補記時点の `EMBEDDING_MODEL` 環境変数値**）として metadata を補記する（マイグレーション）。モデル名を `nomic-embed-text` 固定にせず現在値を参照するのは、過去に既定以外のモデルで運用していた場合の誤タグ付けを避けるため（補記は切替前＝まだ ollama 運用中に初回起動する前提のため現在値が実態と一致する）
   - **0件（空コレクション）** → 過去の登録実績がないため、現在の設定（`EMBEDDING_PROVIDER` / `EMBEDDING_MODEL`）で metadata を新規作成する。これにより、最初から `azure_openai` でデプロイする新規環境で空コレクションを誤って「ollama登録済み」とタグ付けする事故を防ぐ

### 2.4 再登録（reindex）コマンド

```bash
docker compose exec app python -m src.main reindex [--collection {support_emails|product_manuals}] [--yes]
```

- 対象コレクションを現在の設定（`EMBEDDING_PROVIDER` / `EMBEDDING_MODEL`）で再構築する。`--collection` 省略時は全コレクションが対象
- **CLIオプションは既存の `register` コマンド体系に揃える**（`register` は `--yes/-y` を持つ。`src/main.py` 参照）:
  - `--yes` / `-y`: 対象件数・概算表示後の確認をスキップ
  - `--collection`: 対象コレクションを1つに限定（部分失敗からの再開・個別再実行に使う）
- 再登録の入力は、既存コレクションに保存済みの**マスキング済みテキスト**（Chroma の documents）を読み出して使う案を第一候補とする（元ファイル〈eml/PDF〉の再取り込みを不要にできる。実装時に metadata の保全とあわせて検証）

#### 一時コレクション方式と原子性

再登録は一時コレクションを経由し、**どの段階でプロセスが落ちても `{name}` という名前のコレクション（新か旧のいずれか）が常に存在する** swap 順序で行う（コレクション単位で原子的）。

1. `{name}__reindex_tmp` に現在の設定で全ドキュメントを再登録する
2. 全件成功を確認したら、以下の順でswapする（**「先に旧を削除」しない**。削除とリネームは Chroma では別々の2操作で、その間にクラッシュすると `{name}` が消失し、2.3の空コレクション分岐が「新規デプロイ」と誤認してデータ喪失を検出できないため）:
   1. 旧 `{name}` を `{name}__old` にリネームで退避
   2. `{name}__reindex_tmp` を `{name}` にリネームし、新しい metadata を付与
   3. `{name}__old` を削除
   （Chroma のコレクション rename が使えない場合は「新規作成→コピー→旧削除」で代替するが、その場合も『新を作り切ってから旧を消す』順序を守る）
3. 途中失敗（レート制限・ネットワーク断等）時は**一時コレクション/退避コレクションを破棄し、`{name}` は常に有効なコレクションを指す**（データ喪失なし・旧Embeddingで検索継続可能）。クラッシュで `{name}__old` が残った場合は、次回起動時に「`{name}` が存在せず `{name}__old` が存在する」なら退避からの復旧、「両方存在する」なら `{name}__old` の掃除、として回復する

- **複数コレクションにまたがる原子性**: `support_emails` と `product_manuals` は各々独立に上記1〜3を完結させる。全体を1トランザクションにはしない（Chroma に横断トランザクションがないため）。結果として「片方は新Embedding・片方は旧Embedding」の部分状態は起こりうるが、**各コレクション単体では常に整合したEmbedding構成を保つ**
- この部分状態は 2.3 の起動時ガードで検出する。2.3は「現在の設定 vs 各コレクションの metadata」を照合してエラー停止する仕組みであり、未更新コレクション（旧Embeddingのまま）は現在設定と metadata が一致しないため**自動的にエラー停止する**（コレクション同士を突き合わせる別チェックは不要）。エラー時は未更新コレクションを `reindex --collection` で個別再実行するよう案内する
- 進捗表示: 件数（処理済み/総数）を表示し、`--yes` 非指定時は実行前に対象件数とAPIコスト概算を出して確認を挟む。中断（Ctrl+C）時も本番コレクション `{name}` は常に有効（上記swap順序による）。残存した `{name}__reindex_tmp` / `{name}__old` は起動時または次回 reindex 時に掃除する

#### 切替の運用手順

`.env` の `EMBEDDING_PROVIDER` を変更 → `reindex` 実行 → WebUI/CLI 再起動。**WebUI からのランタイム切替は提供しない**（切替に再登録が必須で、UIトグルの気軽さと操作の重さが釣り合わないため。現在の Embedding 構成はサイドバーに表示のみ行う）。

### 2.5 PII保護の前提

クラウド Embedding に送信されるテキストも**マスキング済みであること**が前提。

- 登録経路: 既存フローはマスキング後に `IndexService` へ渡すため構造上安全。ただし reindex 経路（保存済み documents の再読み出し）でもマスク済みテキストのみが対象であることをテストで保証する
- 検索経路: 検索クエリ（ユーザーの質問文）も Embedding されて外部送信されるため、**クエリがマスキング済みであること**を回帰テストで保証する（生成LLMと同様、マスキング前テキストの送信は許容しない）

## 3. 追加依存パッケージ

なし（`langchain-openai` は D-006 で導入済み）。

## 4. 制約・注意点

- モデル名・次元数・料金・APIバージョンは実装時点の最新情報を確認して確定する（本設計書の値は2026-07時点のドラフト）
- Embedding をクラウドへ切り替えると**登録・検索のたびに外部送信が発生する**（生成LLMより高頻度）。マスキング保証テストをリリース条件とする点は D-006 と同様
- ローカル⇔クラウドで検索の当たり方（類似度分布）が変わるため、切替後は `SEARCH_TOP_K` や閾値の再調整が必要になる可能性がある。実装時に代表クエリで検索結果を比較する
- reindex はデータ量に応じて時間とAPIコストがかかる。実行前に対象件数と概算を表示して確認を挟む

### 4.1 実装完了時に追従が必要な確定済みドキュメント

本フェーズは D-006 実装完了後に着手するため、D-006 の glossary 更新時点では本フェーズの概念（`EMBEDDING_PROVIDER` 等）はまだ存在しない。したがって以下は**本フェーズ自身の完了条件**として追従する（D-006 の更新に便乗しない）。

- `settings/glossary.md`: 「Embedding」関連エントリに `EMBEDDING_PROVIDER`（ollama / azure_openai）・Embedding切替・reindex の概念を追記
- `.env.example`: `EMBEDDING_PROVIDER` および `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` の雛形を追記
- `settings/repository-structure.md`: 環境別設定表に Embedding 系の新規変数を追記
- `settings/detailed-design/`（02-rag.md 等）: IndexService/QueryService の Embedding ファクトリ化・起動時ガード・reindex コマンドを実装後の現行動作として反映（既存の更新ルールに従う）

### 4.2 受け入れ基準（リリース条件）

本フェーズの完了は以下をすべて満たすこと（測定可能な形で判定する）:

1. **マスキング回帰テスト合格**: reindex 経路（保存済みdocumentsの再読み出し）・検索クエリ経路の両方で、マスク前テキスト・mapping が外部Embedding APIに渡らないことをテストで確認
2. **起動時ガードの動作確認**: 設定とコレクション metadata が不一致の状態で `IndexService`/`QueryService` を初期化するとエラー停止し、案内文が出ることをテストで確認
3. **原子性の確認**: reindex を意図的に途中失敗させたとき、`{name}` コレクションが常に有効（新か旧）で検索が継続できることを確認。swap各段階での中断（旧退避後・新リネーム後）からの回復も確認
4. **一時コレクション掃除の確認**: 中断後に残った `{name}__reindex_tmp` / `{name}__old` が起動時または次回 reindex 時に掃除されることを確認
5. **検索品質の目視比較**: 切替前後で代表クエリ N件（実装時に選定、目安5〜10件）を実行し、期待するマニュアル/メールがヒットし続けることをレビュー承認する（合格基準＝業務上必要な参照が上位に出ること。定量スコアではなくレビュアー判断でよい）
