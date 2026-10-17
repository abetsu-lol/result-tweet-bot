# result-tweet-bot

毎日定時に実行される Python ジョブ（Google Cloud Functions 1st gen, Pub/Sub トリガー）と、そのインフラ一式。

```
cloud_function/   アプリ本体（エントリポイント: daily_job(event, context)）
terraform/        Cloud Function / Pub/Sub / Cloud Scheduler / Workload Identity Federation
scripts/          tfstate 用バケットの作成（bootstrap）・パッケージング用スクリプト
.github/workflows/deploy.yml  main への push で terraform apply
```

コードには特定の環境の値（プロジェクト ID・バケット名など）を含めていません。値はすべて GitHub リポジトリの設定から渡します。
GitHub Actions は、**ワークフローを実行するリポジトリに設定された Variables / Secrets の GCP プロジェクト**にデプロイします。
fork（または clone して自分のリポジトリに push）し、以下の手順で設定すれば自分の環境で同じように動かせます。

## 設定項目

デプロイに必要な値はすべて GitHub リポジトリの設定（Settings → Secrets and variables → Actions）に置きます。
リポジトリ内に環境ごとの設定ファイル（tfvars など）はありません。

| 種類 | 名前 | 値 | 取得元 |
| --- | --- | --- | --- |
| Variable | `DEPLOY_ENABLED` | `true` | 未設定のリポジトリではデプロイジョブはスキップされる |
| Variable | `GCP_PROJECT_ID` | GCP プロジェクト ID | |
| Variable | `GCP_REGION` | リージョン（例: `asia-northeast1`） | |
| Variable | `TF_STATE_BUCKET` | tfstate 用バケット名 | `scripts/bootstrap.sh` の出力 |
| Secret | `GCP_WORKLOAD_PROVIDER` | WIF プロバイダのフルリソース名 | 初回 apply 後の `terraform output -raw wif_provider` |
| Secret | `GCP_SA_EMAIL` | GitHub Actions 用サービスアカウントのメールアドレス | 初回 apply 後の `terraform output -raw github_actions_sa_email` |

Terraform の変数との対応:

| Terraform 変数 | 値の出どころ |
| --- | --- |
| `project` | `GCP_PROJECT_ID` |
| `region` | `GCP_REGION` |
| `github_repository` | ワークフローを実行しているリポジトリ（`github.repository`）を自動で使用 |
| `service_name`・`deploy_branch`・`ci_roles` ほか | `terraform/variables.tf` の既定値。変える場合は既定値を編集して push |

## 自分の環境にデプロイする

前提: GCP プロジェクト（課金有効）、`gcloud`、Terraform >= 1.5、GitHub リポジトリ、bash（Windows では Git Bash）。

### 1. tfstate 用バケットを作成（ローカル・初回のみ）

```bash
gcloud auth login
./scripts/bootstrap.sh YOUR_PROJECT_ID [REGION]   # バケット名は TFSTATE_BUCKET で変更可（既定: terraform-state-<PROJECT>）
```

バージョニング有効のバケットを作成し、`TF_STATE_BUCKET` に設定する値を表示します。
何度実行しても安全です（既存バケットは設定の更新のみで、state には触れません）。
state の過去の版はバージョニングで保持され、古い版（新しい版が 5 つ以上ある、または古い版になって 90 日経過）だけが自動削除されます。
誤って壊した場合は `gcloud storage ls -a gs://<bucket>/terraform/state/` で過去の版を確認して復元できます。

### 2. 初回 apply（ローカル・初回のみ）

CI が GCP に認証するための WIF とサービスアカウントはこの apply で作られるため、最初の 1 回だけはローカルから実行します。
値はファイルに保存せず、引数で渡します。

```bash
gcloud auth application-default login
./scripts/package_function.sh
cd terraform
terraform init -backend-config="bucket=YOUR_TF_STATE_BUCKET" -backend-config="prefix=terraform/state"
terraform apply   -var="project=YOUR_PROJECT_ID"   -var="region=asia-northeast1"   -var="github_repository=OWNER/REPO"     # このリポジトリ。GitHub 上の名前と完全に一致させる
terraform output -raw wif_provider; echo
terraform output -raw github_actions_sa_email; echo
```

### 3. GitHub リポジトリの設定

[設定項目](#設定項目) の Variables / Secrets をすべて設定します。
fork の場合は Actions タブからワークフローを有効にしてください（fork では既定で無効）。

### 4. 以降

`main` に push すると `.github/workflows/deploy.yml` が `cloud_function/` を zip にして `terraform apply` します。
ソースが変わると GCS 上のオブジェクト名（内容ハッシュ）が変わり、関数が再デプロイされます。
インフラの変更も同様に push で反映し、ローカルからの plan / apply は行いません。

## セキュリティ

- Workload Identity Federation で、`github_repository` の `deploy_branch`（既定 `main`）で動くワークフローだけが認証できます。fork や Pull Request からは認証できません。
- ワークフローは `pull_request` では実行しません。
- CI 用サービスアカウントには `terraform apply` のため `roles/editor`・`roles/iam.securityAdmin`・`roles/iam.workloadIdentityPoolAdmin` を付与しています（`ci_roles` で変更可能）。IAM を管理できる強い権限なので、個人用プロジェクトで使うことを想定しています。

## ローカルでの動作確認

```bash
cd cloud_function
python -c "import main; print(main.daily_job({}, None))"
```
