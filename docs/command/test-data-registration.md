# テストデータ登録コマンド

## 概要

プロトタイプの動作確認用テストデータ（パスワードリセットに関する問い合わせ→回答ペア）の登録コマンド。

## 前提条件

- Docker コンテナが起動していること（`docker compose up -d`）
- ホストOS上で Ollama が起動していること（`OLLAMA_HOST=0.0.0.0 ollama serve`）
- nomic-embed-text モデルがダウンロード済みであること（`ollama pull nomic-embed-text`）

## 登録コマンド

### メール1（問い合わせ）

```bash
cat > /tmp/mail1.txt <<'EOF'
件名: パスワードリセットについて

株式会社テックサポート 御中

お世話になっております。株式会社山田商事の山田太郎（yamada-taro@yamada-shoji.co.jp）です。

弊社で利用しているCloudManageProのアカウントですが、パスワードを忘れてしまいログインできなくなりました。
パスワードをリセットする方法を教えていただけますでしょうか。

対象アカウント: yamada-taro@yamada-shoji.co.jp
利用プラン: ビジネスプラン
電話番号: 03-5555-1234

お手数ですが、よろしくお願いいたします。

山田太郎
〒100-0001 東京都千代田区1-1-1
EOF

cat /tmp/mail1.txt | docker compose exec -T app python -m src.main register --yes
```

### メール2（回答）

```bash
cat > /tmp/mail2.txt <<'EOF'
件名: Re: パスワードリセットについて

山田太郎様

お問い合わせありがとうございます。株式会社テックサポートの佐藤花子です。

パスワードのリセット方法をご案内いたします。

【パスワードリセット手順】
1. CloudManageProのログイン画面（https://app.cloudmanagepro.example.com）にアクセスしてください
2. 「パスワードをお忘れの方」リンクをクリックしてください
3. 登録済みのメールアドレスを入力し「送信」を押してください
4. 届いたメールに記載のURLをクリックし、新しいパスワードを設定してください

※リセットメールが届かない場合は、迷惑メールフォルダをご確認ください。
※パスワードは8文字以上、英数字・記号を含む必要があります。
※リセットURLの有効期限は24時間です。

上記で解決しない場合は、管理者権限でのリセットも可能ですので改めてご連絡ください。

よろしくお願いいたします。

佐藤花子
株式会社テックサポート カスタマーサポート部
03-5555-9999
sato-hanako@techsupport.co.jp
EOF

cat /tmp/mail2.txt | docker compose exec -T app python -m src.main register --yes
```

### 動作確認（質問）

```bash
docker compose exec -T app python -m src.main ask "パスワードのリセット方法は？"
```

## 注意事項

- `docker compose exec` でパイプ入力する場合は `-T` フラグ必須（TTY無効化）
- `-it` を使うとヒアドキュメント・パイプで「the input device is not a TTY」エラーになる
- メール文にはPII（人名、メールアドレス、電話番号、郵便番号）が意図的に含まれており、マスキングの動作確認にも使用する
