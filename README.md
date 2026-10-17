# result-tweet-bot

毎日定時に実行される Python ジョブ（Google Cloud Functions, Pub/Sub トリガー）。

## 構成

- `cloud_function/main.py` — エントリポイント `daily_job(event, context)`

インフラ定義とデプロイは別リポジトリ（非公開）で管理しており、このリポジトリの `cloud_function/` を zip にして Cloud Function としてデプロイしています。
このリポジトリには GCP のプロジェクト情報や認証情報を置かないでください。

## ローカルでの動作確認

```bash
cd cloud_function
python -c "import main; print(main.daily_job({}, None))"
```
