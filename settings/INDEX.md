# 設計書インデックス

このフォルダにはカスタマーサポート回答生成システムの設計書を格納する。

- フェーズ別設計書（連番付き）は [phases/](phases/) 配下に置く
- マスター仕様書（PRD等、`/init-docs` で生成）は本フォルダ直下に置く（/init-docs 系スキルがこのパスを前提とするため移動禁止）
- 現行実装のスナップショット詳細設計書（モジュール別）は [detailed-design/](detailed-design/) 配下に置く（入口は [detailed-design/README.md](detailed-design/README.md)）

## 設計書一覧

| ID | ファイル名 | フェーズ | 概要 | ステータス | 最終更新 |
|---|---|---|---|---|---|
| D-001 | [01-prototype.md](phases/01-prototype.md) | プロトタイプ | テキスト入力→マスキング→RAG登録→CUI回答生成 | 作成中 | 2026-06-17 |
| D-002 | [02-update-eml-reader.md](phases/02-update-eml-reader.md) | 第1弾 | .emlファイルからメール内容を読み取り | 実装済み | 2026-07-07 |
| D-003 | [03-update-pdf-manual.md](phases/03-update-pdf-manual.md) | 第2弾 | 製品マニュアル（PDF）の取り込み | 実装済み | 2026-07-08 |
| D-004 | [04-update-web-ui.md](phases/04-update-web-ui.md) | 第3弾 | GUIベース（Webアプリ）の回答生成画面 | 実装済み | 2026-07-08 |
| D-005 | [05-update-zendesk.md](phases/05-update-zendesk.md) | 第4弾 | Zendesk APIからメール内容を読み取り | 作成中 | 2026-06-17 |
| D-006 | [06-update-llm-switch.md](phases/06-update-llm-switch.md) | 第5弾 | 生成LLMマルチプロバイダ切替（Ollama / Claude / Azure OpenAI） | レビュー | 2026-07-20 |
| D-007 | [07-update-embedding-switch.md](phases/07-update-embedding-switch.md) | 第6弾 | Embedding切替（ローカル/Azure OpenAI。コレクション整合ガード・reindex） | レビュー | 2026-07-20 |
| - | [product-requirements.md](product-requirements.md) | - | プロダクト要求定義書（PRD） | 確定 | 2026-06-19 |
| - | [functional-design.md](functional-design.md) | - | 機能設計書 | 確定 | 2026-06-19 |
| - | [architecture.md](architecture.md) | - | アーキテクチャ設計書 | 確定 | 2026-06-19 |
| - | [repository-structure.md](repository-structure.md) | - | リポジトリ構造定義書 | 確定 | 2026-08-08 |
| - | [development-guidelines.md](development-guidelines.md) | - | 開発ガイドライン | 確定 | 2026-06-19 |
| - | [glossary.md](glossary.md) | - | 用語集 | 確定 | 2026-06-19 |
| - | [detailed-design/README.md](detailed-design/README.md) | - | 詳細設計書（現行実装スナップショット。モジュール別6ファイル、D-001〜D-004 実装時点） | 確定 | 2026-07-15 |

## 命名規則

- `01`: プロトタイプ
- `02`: 第1弾アップデート（.eml読み取り）
- `03`: 第2弾アップデート（PDFマニュアル取り込み）
- `04`: 第3弾アップデート（WebアプリUI）
- `05`: 第4弾アップデート（Zendesk API連携）
- `06`: 第5弾アップデート（生成LLMマルチプロバイダ切替。D-004から分離、2026-07-20 に Azure OpenAI 対応へ拡張）
- `07`: 第6弾アップデート（Embedding切替。再登録を伴うため D-006 から分離）
- `90-99`: 横断的な設計（共通基盤・非機能要件等）
- ファイル名なし: マスター仕様書（PRD等、`/init-docs` で生成）
- `detailed-design/`: 現行実装のスナップショット詳細設計書（モジュール別。フェーズ別の差分設計書と異なり、実装の進行に合わせて更新し続ける）
- 旧 `00`（D-000 マスター設計書）は2026-07-08に廃止。内容はマスター仕様書群に引き継ぎ済み（固有分は PRD・architecture.md・development-guidelines.md へ移植）

## ステータス定義

| ステータス | 意味 |
|---|---|
| 作成中 | 初版作成中 |
| レビュー | レビュー待ち |
| 確定 | 内容確定・実装可能 |
| 実装済み | 実装完了 |
| 廃止 | 設計変更により無効化 |
