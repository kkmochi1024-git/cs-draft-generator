# Docker exec -Tフラグの必要性

- **日時**: 2026-06-21
- **参加者**: ユーザー, Claude

## 背景・目的

プロトタイプの動作確認で `docker compose exec` にヒアドキュメントやパイプで標準入力を渡す際、「the input device is not a TTY」エラーが繰り返し発生した。根本原因と正しい使い方を整理する。

## 議論の要点

### 問題の発生

- **事象**: `docker compose exec app python -m src.main register --yes <<'EOF' ... EOF` で「the input device is not a TTY」エラー
- **原因**: `docker compose exec` はデフォルトでTTY（端末）を割り当てる。ヒアドキュメントやパイプで標準入力を渡す場合、入力元が端末ではないため矛盾が起きる
- **結論**: `-T` フラグでTTY割り当てを無効にする

### 正しいコマンドの使い分け

- **対話モード**（人間がキーボード入力）: `docker compose exec -it app ...`
- **パイプ/ヒアドキュメント**（プログラム的入力）: `docker compose exec -T app ...`
- `-it` と `-T` は排他。同時に使わない

### 入力方式の改善

- **変更前**: `sys.stdin.read()` で入力を受け取る設計 → Docker tty環境でCtrl+Dが効かない
- **変更後**: `input()` ループで1行ずつ読み取り、空行で入力終了する設計に変更

## 決定事項

- ヒアドキュメント・パイプでの入力時は必ず `-T` フラグを使用する
- CLAUDE.md のコマンド例も `-T` を使う形に統一すべき（対話モードのみ `-it`）
- 長文テキストの登録は一時ファイル経由（`cat /tmp/file.txt | docker compose exec -T app ...`）が確実

## 未決事項・次のアクション

- [ ] CLAUDE.md のコマンド例を `-T` / `-it` の使い分けで整理する
