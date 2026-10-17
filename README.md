# result-tweet-bot

毎日定時に実行される Python ジョブ（Google Cloud Functions 1st gen, Pub/Sub トリガー）と、そのインフラ一式。

```
cloud_function/   アプリ本体（エントリポイント: daily_job(event, context)）
terraform/        Cloud Function / Pub/Sub / Cloud Scheduler / Workload Identity Federation
scripts/          tfstate 用バケットの作成（bootstrap）・パッケージング用スクリプト
.github/workflows/deploy.yml  main への push で terraform apply
```

コードには特定の環境の値（プロジェクト ID・バケット名など）を含めていません。
GitHub Actions は、**ワークフローを実行するリポジトリに設定された Variables / Secrets の GCP プロジェクト**にデプロイします。
fork（または clone して自分のリポジトリに push）し、以下の手順で設定すれば自分の環境で同じように動かせます。

## 自分の環境にデプロイする

前提: GCP プロジェクト（課金有効）、`gcloud`、Terraform >= 1.5、GitHub リポジトリ。

### 1. 初回セットアップ（ローカル）

CI が GCP に認証するための WIF とサービスアカウントはまだ存在しないので、最初の 1 回だけローカルから作成します。

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# tfstate 用バケット（バージョニング有効）を作成し、terraform/backend.hcl を生成
# 引数: [PROJECT] [REGION]、バケット名は TFSTATE_BUCKET で変更可（既定: terraform-state-<PROJECT>）
./scripts/bootstrap.sh                 # PowerShell: .\scripts\bootstrap.ps1 [-Project ...] [-Region ...] [-Bucket ...]

# 変数を設定（github_repository は自分のリポジトリ "owner/repo"）
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

./scripts/package_function.sh          # PowerShell: .\scripts\package_function.ps1
cd terraform
terraform init -backend-config=backend.hcl
terraform apply
terraform output                       # wif_provider と github_actions_sa_email を控える
```

`terraform.tfvars`・`backend.hcl`・tfstate は Git 管理外です。

bootstrap は何度実行しても安全です（既存バケットは設定の更新のみで、state には触れません）。
state の過去の版はバージョニングで保持され、古い版（新しい版が 5 つ以上ある、または古い版になって 90 日経過）だけが自動削除されます。
誤って壊した場合は `gcloud storage ls -a gs://<bucket>/terraform/state/` で過去の版を確認して復元できます。

### 2. GitHub リポジトリの設定

Settings → Secrets and variables → Actions:

| 種類 | 名前 | 値 |
| --- | --- | --- |
| Variable | `DEPLOY_ENABLED` | `true`（未設定のリポジトリではデプロイジョブはスキップされる） |
| Variable | `GCP_PROJECT_ID` | GCP プロジェクト ID |
| Variable | `GCP_REGION` | リージョン（例: `asia-northeast1`） |
| Variable | `TF_STATE_BUCKET` | `terraform/backend.hcl` の `bucket` |
| Secret | `GCP_WORKLOAD_PROVIDER` | `terraform output wif_provider` |
| Secret | `GCP_SA_EMAIL` | `terraform output github_actions_sa_email` |

fork の場合は Actions タブからワークフローを有効にしてください（fork では既定で無効）。

### 3. 以降

`main` に push すると `.github/workflows/deploy.yml` が `cloud_function/` を zip にして `terraform apply` します。
ソースが変わると GCS 上のオブジェクト名（内容ハッシュ）が変わり、関数が再デプロイされます。

## セキュリティ

- Workload Identity Federation で、`github_repository` の `deploy_branch`（既定 `main`）で動くワークフローだけが認証できます。fork や Pull Request からは認証できません。
- ワークフローは `pull_request` では実行しません。
- CI 用サービスアカウントには `terraform apply` のため `roles/editor`・`roles/iam.securityAdmin`・`roles/iam.workloadIdentityPoolAdmin` を付与しています（`ci_roles` で変更可能）。IAM を管理できる強い権限なので、個人用プロジェクトで使うことを想定しています。

## ローカルでの動作確認

```bash
cd cloud_function
python -c "import main; print(main.daily_job({}, None))"
```
