# D-006: 第5弾アップデート - 生成LLMマルチプロバイダ切替（クラウド対応）

| 項目 | 値 |
|---|---|
| フェーズ | 第5弾アップデート |
| ステータス | レビュー |
| 作成日 | 2026-07-08（2026-07-20 マルチプロバイダ対応へ拡張） |
| 前提 | [D-004 WebUI](04-update-web-ui.md) が実装済みであること |
| 経緯 | D-004 のスコープから分離。当初 D-004 にUIトグルのみ記載されていたが、バックエンド側のクラウド切替（`config.LLM_BACKEND` は定義のみで未使用、`QueryService` は `ChatOllama` 固定）が未実装であり、UIと実装をセットで扱うため独立フェーズとした。**2026-07-20: ユーザー要望により「Claude単体」から「複数プロバイダ（Anthropic Claude / Azure OpenAI）」対応へ拡張。Embedding切替は性質が異なる（既存ベクトルとの互換性喪失・再登録を伴う）ため [D-007](07-update-embedding-switch.md) に分離** |

## 1. ゴール

回答生成に使うLLMを、ローカル（Ollama / Gemma）と複数のクラウドプロバイダ（Anthropic Claude / Azure OpenAI）で切り替えられるようにする。
通常はローカルで運用し、回答品質を優先したいケースでクラウドを選択できるようにする。
プロバイダの追加が「ファクトリ関数＋設定＋UI選択肢」の追加だけで完結する構造にし、将来のプロバイダ追加に備える。

### スコープ内

- 生成LLMのプロバイダ切替（環境変数 `LLM_PROVIDER` + D-004 UIの選択）。**CLI（`main.py ask` / `chat`）と WebUI は `QueryService` を共用するため、ファクトリ導入により CLI も同じ切替の恩恵を受ける**
- Anthropic Claude 連携（`langchain-anthropic`）
- Azure OpenAI 連携（`langchain-openai` の `AzureChatOpenAI`）
- APIキー等の `.env` 管理
- クラウド送信前のPIIマスキング保証の回帰テスト（全クラウドプロバイダ共通）
- 接続・認証エラー文言のプロバイダ非依存化（現行 `_wrap_connection_error` は Ollama 固定文言のため）

### スコープ外

- Embedding のクラウド化・切替 → **[D-007](07-update-embedding-switch.md)（第6弾）で対応**。Embeddingモデルを変えると既存ChromaDBの登録済みベクトルと互換性がなくなり全再登録が必要になるため、生成LLM切替とはリスクの性質が異なる
- コスト管理・利用量ダッシュボード → 将来検討
- OpenAI（非Azure）・Gemini 等のさらなるプロバイダ追加 → 将来検討（本フェーズの構造で追加自体は容易にしておく）

## 2. 設計方針（ドラフト）

### 2.1 設定体系

未使用だった `LLM_BACKEND`（local/cloud の2値）を廃止し、プロバイダ名を直接指定する `LLM_PROVIDER` に置き換える。

| 環境変数 | 値 | 説明 |
|---|---|---|
| `LLM_PROVIDER` | `ollama`（既定） / `anthropic` / `azure_openai` | 生成LLMのプロバイダ |
| `ANTHROPIC_API_KEY` | — | Claude 用APIキー（`.env`） |
| `ANTHROPIC_MODEL_NAME` | 例: 実装時に最新モデルを確認 | Claude のモデル名 |
| `AZURE_OPENAI_API_KEY` | — | Azure OpenAI 用APIキー（`.env`） |
| `AZURE_OPENAI_ENDPOINT` | `https://{resource}.openai.azure.com/` | Azure OpenAI リソースのエンドポイント |
| `AZURE_OPENAI_API_VERSION` | 実装時に確認 | APIバージョン |
| `AZURE_OPENAI_DEPLOYMENT` | — | デプロイメント名（Azureはモデル名でなくデプロイメント単位で指定する） |

### 2.2 LLMファクトリ

現行 `QueryService.__init__` 内の `ChatOllama` 直接生成（`src/rag/query_service.py` 27-32行）をやめ、`LLM_PROVIDER` に応じてLLMを生成するファクトリに置き換える。プロバイダ分岐はこのファクトリに閉じ込め、`QueryService` 側にはプロバイダ条件分岐を漏らさない。

**未知のプロバイダ名はサイレントにローカルへフォールバックせず、明確なエラーで起動を止める**（ユーザーが「クラウドに切り替えたつもり」でローカル品質の回答を得る事故を防ぐため）。したがって `ollama` も明示分岐にし、既定の `return ChatOllama(...)` に未知プロバイダが落ちる構造にはしない。

APIキー・エンドポイントはコード例で明示的に渡していないが、これは各SDKが環境変数（`ANTHROPIC_API_KEY` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT`）から自動読み込みする前提の意図的な省略（設定漏れではない）。

```python
# src/rag/llm_factory.py（新規・案）
# APIキー・エンドポイントは各SDKが環境変数から自動読み込みする（明示引数は省略）
def create_llm(provider: str):
    if provider == "ollama":
        return ChatOllama(
            model=config.MODEL_NAME,
            base_url=config.OLLAMA_BASE_URL,
            temperature=config.TEMPERATURE,
            num_predict=config.MAX_TOKENS,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.ANTHROPIC_MODEL_NAME,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        )
    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=config.AZURE_OPENAI_DEPLOYMENT,
            api_version=config.AZURE_OPENAI_API_VERSION,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        )
    raise ValueError(
        f"未知の LLM_PROVIDER です: {provider!r}（有効値: ollama / anthropic / azure_openai）"
    )
```

### 2.2.1 接続・認証エラーの一般化

現行 `QueryService._wrap_connection_error`（`query_service.py` 114-122行）は、例外文字列/クラス名に `connect` / `connection` を含む場合に **Ollama 固定文言（「Ollamaに接続できません… ollama serve」）** へ変換する。クラウドプロバイダ利用時のエラー（APIキー不正・認証失敗・レート制限・タイムアウト・Azureのデプロイメント名誤り等）はこの条件に当てはまらない、あるいは当てはまっても誤った案内になる。

- エラー変換をプロバイダ非依存化する。少なくとも「現在のプロバイダ名」を文言に含め、Ollama固定の案内文を出すのは `provider == "ollama"` のときに限定する
- 実装案: ファクトリが生成したプロバイダ種別を `QueryService` が保持し、`_wrap_connection_error` がプロバイダに応じた案内文（ローカル→ollama起動確認 / クラウド→APIキー・エンドポイント・レート制限の確認）を返す

### 2.3 PII保護の前提（本システムの根幹）

クラウドに送信されるのは**マスキング済みプロンプトのみ**であること。既存の `QueryService.ask()` はマスキング後テキストでプロンプトを構築しており、unmask はLLM応答受信後にローカルで行うため、構造上PIIは外部送信されない。
実装時は「クラウド経路でマスキング前テキスト・mapping（トークン→原文の対応表）が送信されないこと」をテストで保証する。**このテストはプロバイダ個別ではなくファクトリ経由の共通経路に対して書き、プロバイダ追加時に自動的にカバーされるようにする**。

### 2.4 D-004 UIへの追加

サイドバーにプロバイダ選択ラジオボタンを追加する（D-004 初版のモックアップから移設・3択に拡張）。

```
◆ 設定
LLMプロバイダ:
○ ローカル (Gemma)
○ クラウド (Claude) ※APIキー設定時のみ選択可
○ クラウド (Azure OpenAI) ※接続設定時のみ選択可
```

- 各クラウドプロバイダは必要な環境変数（`ANTHROPIC_API_KEY` / `AZURE_OPENAI_API_KEY`+`AZURE_OPENAI_ENDPOINT`+`AZURE_OPENAI_DEPLOYMENT`）が揃っている場合のみ選択可とし、未設定時は無効化して設定方法をツールチップで案内する
- 現在どのプロバイダ・モデルで回答が生成されたかを回答横に表示する（監査性のため）

#### UI選択と QueryService の結線（ランタイム切替の方式）

本フェーズのUI選択は**表示のみ**ではなく、セッション中に実際にプロバイダを切り替える動的選択とする。現行実装は WebUI 起動時に `get_services()` が `QueryService(masking_service=masking)` を一度だけ生成し、`QueryService.__init__` がコンストラクタで `self._llm` を一度だけ生成する構造（`src/app/main.py` の `get_services`、`query_service.py` 14-32行）のため、以下の結線を追加する。

1. `LLM_PROVIDER` を「既定値（初期選択）」とし、UIラジオの選択値を `st.session_state.llm_provider` に保持する
2. `QueryService.__init__` に `llm_provider: str | None = None` 引数を追加し、内部で `create_llm(llm_provider or config.LLM_PROVIDER)` を呼ぶ（CLI はこの引数を渡さず環境変数どおりに動く＝後方互換）
3. UIでプロバイダが変更されたら LLM を差し替える。ただし**現行 `get_services()` は `MaskingService`（GiNZAロード）と `QueryService` を1つの `@st.cache_resource` にまとめてキャッシュしている**（重い初期化を避けるため）。この関数のキャッシュキーにプロバイダを含めると、プロバイダ切替のたびに関数全体が再実行され GiNZA まで再ロードされ、複数の `MaskingService` がプロセス内に重複して残る。これを避けるため `get_services()` を分割する:
   - `MaskingService` は引数なしの `@st.cache_resource` で常に共有（プロバイダに依存しない）
   - `QueryService`（またはその内部 `_llm`）はプロバイダをキーにした別の `@st.cache_resource` でキャッシュする。検索用 embedding・vectorstore も本フェーズでは Ollama 固定（D-007まで不変）のため、プロバイダ切替で作り直すのは LLM 部分のみに限定する
4. `QueryService` に「LLM のみを差し替える」経路を用意する（例: `set_llm_provider(provider)` で `self._llm = create_llm(provider)` を再代入）と、embedding/vectorstore を保持したまま LLM だけ切り替えられ、再生成コストを最小化できる

### 2.5 ストリーミング

D-004 で追加する `ask_stream()` は全プロバイダで動作させる（`ChatAnthropic`・`AzureChatOpenAI` とも `stream()` に対応）。チャンクの型差異（`AIMessageChunk` / str）は既存のローカル対応と同様にファクトリ利用側で吸収する。

## 3. 追加依存パッケージ

```toml
dependencies = [
    "langchain-anthropic>=0.3",
    "langchain-openai>=0.3",
]
```

## 4. 制約・注意点

- APIキーは `.env` で管理し、Gitにコミットしない（既存の開発ルールに準拠）
- クラウド利用時は外部送信が発生するため、マスキング機構の回帰テストをリリース条件とする
- モデル名・料金・レート制限・APIバージョンは実装時点の最新情報を確認して確定する（本設計書の値は2026-07時点のドラフト）
- Azure OpenAI はリソースのリージョン・デプロイメント名を環境変数（`AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT`）で指定する。サブスクリプション・リージョンは導入環境に応じて選定する
- プロバイダごとに `SYSTEM_PROMPT` の効き方（応答スタイル）が変わる可能性があるため、実装時に全プロバイダで出力品質を比較する

### 4.1 実装完了時に追従が必要な確定済みドキュメント

`LLM_BACKEND`（local/cloud 2値）の廃止と `LLM_PROVIDER`（3値）への置換に伴い、以下の「確定」ステータスの記述が実装後に事実と乖離する。実装フェーズの完了条件（tasklist）に含める。

- `settings/glossary.md`: 「LLMバックエンド」エントリを「LLMプロバイダ」に改称し（旧語は「→LLMプロバイダ参照」として残す）、プロバイダ（ollama / anthropic / azure_openai）ベースの定義へ更新。「Claude API」エントリも並列プロバイダの一つとして整理
- `settings/functional-design.md`: 状態遷移図と説明文の「切替は環境変数 `LLM_BACKEND` または UIトグルで行う」を更新。あわせて**同図の「マスキング精度95%達成で切替」という自動切替の描写と、本設計の「手動でプロバイダを選ぶ」運用像の食い違いを解消する**（本フェーズの正は「手動選択」。精度は切替の前提条件ではなくクラウド送信可否の判断材料と整理する）
- `settings/repository-structure.md`: 環境別設定表の `LLM_BACKEND` 列を `LLM_PROVIDER` と新規変数群に更新
- `.env.example`: `LLM_BACKEND=local` を削除し、`LLM_PROVIDER` および新規変数（`ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL_NAME` / `AZURE_OPENAI_*`）の雛形を追記
- `settings/detailed-design/`（02-rag.md 等）: 実装後スナップショットのため、実装完了時に現行動作へ更新（既存の更新ルールに従う）

### 4.2 受け入れ基準（リリース条件）

本フェーズの完了は以下をすべて満たすこと（測定可能な形で判定する。D-007 の受け入れ基準と対称に構造化する）:

1. **マスキング回帰テスト合格**: ファクトリ共通経路で、マスク前テキスト・mapping が外部LLM APIに渡らないことをテストで確認（プロバイダ個別ではなく共通経路に対して書く）
2. **未知プロバイダのエラー停止**: 未知の `LLM_PROVIDER` 指定時に `create_llm` が `ValueError` で停止し、案内文が出ることを確認
3. **全プロバイダの動作確認**: ollama / anthropic / azure_openai それぞれで `ask` と `ask_stream`（ストリーミング）が動作することを確認
4. **UIの選択可否制御**: APIキー等が未設定のクラウドプロバイダが UI 上で選択不可（無効化）になることを確認
5. **プロバイダ非依存エラー文言**: 接続/認証エラー時に、現在のプロバイダに応じた案内文（Ollama起動確認 / APIキー・エンドポイント・レート制限の確認）が出ることを確認
