# result-tweet-bot

毎日定時に実行される Python ジョブ（Google Cloud Functions 1st gen, Pub/Sub トリガー）と、そのインフラ一式。

```
cloud_function/   アプリ本体（エントリポイント: daily_job(event, context)）
terraform/
  bootstrap/prod/     CI の前提となるリソース（WIF・デプロイ用サービスアカウント）。ローカルから apply
  environments/prod/  アプリのリソース（Cloud Function・Pub/Sub・Cloud Scheduler）。CI から apply
  modules/scheduled_function/  Cloud Function + Pub/Sub + Cloud Scheduler + イメージ用 Artifact Registry（最新 2 件のみ保持）
  modules/github_actions_wif/  GitHub Actions 用 Workload Identity Federation とデプロイ用サービスアカウント
  modules/function_build_iam/  関数のビルドに Cloud Build が使うサービスアカウント（Compute Engine のデフォルト SA）の権限
  modules/function_runtime/    関数の実行用サービスアカウント・Secret Manager の Secret（器のみ）・戦績データ用バケットと権限
scripts/          tfstate 用バケットの作成（bootstrap）・パッケージング用スクリプト
.github/workflows/deploy.yml  main への push で terraform/environments/prod を apply
```

コードには特定の環境の値（プロジェクト ID・バケット名など）を含めていません。値はすべて GitHub リポジトリの設定から渡します。
GitHub Actions は、**ワークフローを実行するリポジトリに設定された Variables の GCP プロジェクト**にデプロイします。
fork（または clone して自分のリポジトリに push）し、以下の手順で設定すれば自分の環境で同じように動かせます。

## 構成の考え方

| | 内容 | apply する場所 | state（tfstate 用バケット内の prefix） |
| --- | --- | --- | --- |
| tfstate 用バケット | `scripts/bootstrap.sh`（gcloud） | ローカル | — |
| `terraform/bootstrap/prod` | WIF プール / プロバイダ、デプロイ用サービスアカウントとその権限、関数のビルドに使うサービスアカウントの権限、関数の実行用サービスアカウント・Secret・戦績データ用バケット | ローカル（初回とまれな変更のみ） | `terraform/bootstrap` |
| `terraform/environments/prod` | Cloud Function・Pub/Sub・Cloud Scheduler | CI | `terraform/state` |

CI の認証情報と IAM は CI の管理対象外にしているため、デプロイ用サービスアカウントにはプロジェクトの IAM を変更する権限がありません。

## 設定項目

デプロイに必要な値はすべて GitHub リポジトリの設定（Settings → Secrets and variables → Actions / Settings → Environments）に置きます。
リポジトリ内に環境ごとの設定ファイル（tfvars など）はありません。
機密ではない値は Variables（公開リポジトリでは Actions のログに値が表示されます）、API キーなどは Secrets に置きます。

Environment `prod` を作成し、Deployment branches を `main` のみに制限したうえで、以下を設定します。

| 置き場所 | 名前 | 値 | 取得元 |
| --- | --- | --- | --- |
| リポジトリの Variable | `DEPLOY_ENABLED` | `true` | 未設定のリポジトリではデプロイジョブはスキップされる。ジョブの `if` で参照するため Environment ではなくリポジトリに置く |
| Environment `prod` の Variable | `GCP_PROJECT_ID` | GCP プロジェクト ID | |
| Environment `prod` の Variable | `GCP_REGION` | リージョン（例: `asia-northeast1`） | |
| Environment `prod` の Variable | `TF_STATE_BUCKET` | tfstate 用バケット名 | `scripts/bootstrap.sh` の出力 |
| Environment `prod` の Variable | `GCP_WORKLOAD_PROVIDER` | WIF プロバイダのフルリソース名 | `terraform/bootstrap/prod` の `terraform output -raw wif_provider` |
| Environment `prod` の Variable | `GCP_SA_EMAIL` | デプロイ用サービスアカウントのメールアドレス | `terraform/bootstrap/prod` の `terraform output -raw deployer_service_account_email` |
| Environment `prod` の Secret | `RIOT_API_KEY` | Riot Games の API キー | [Secret の登録と更新](#secret-の登録と更新) |
| Environment `prod` の Secret | `X_APP_CREDENTIALS` | X アプリの Consumer Key / Secret（JSON） | 同上 |
| Environment `prod` の Secret | `ACCOUNTS` | 対象の Riot アカウントと X アカウントのセットの配列（JSON） | 同上 |

Terraform の変数との対応:

| Terraform 変数 | 値の出どころ |
| --- | --- |
| `environments/prod`: `project` / `region` | `GCP_PROJECT_ID` / `GCP_REGION` |
| `environments/prod`: `riot_api_key` / `x_app_credentials` / `accounts` | Secrets（`TF_VAR_*`）。書き込み専用で Secret Manager に書き込まれ、plan と state には残らない |
| `bootstrap/prod`: `project` / `github_repository` | ローカルでの apply 時に `-var` で指定 |
| リソース名（`name`）・スケジュール・デプロイ用ブランチ・デプロイ用サービスアカウントのロールほか | 各ルートの `main.tf` のモジュール引数。変える場合は編集する |

## 自分の環境にデプロイする

前提: GCP プロジェクト（課金有効）、`gcloud`、`gh`、Terraform >= 1.11、GitHub リポジトリ、bash（Windows では Git Bash）。
ローカルでの作業はプロジェクトのオーナー権限で行います。

### 1. tfstate 用バケットを作成（ローカル・初回のみ）

```bash
gcloud auth login
./scripts/bootstrap.sh YOUR_PROJECT_ID [REGION]   # バケット名は TFSTATE_BUCKET で変更可（既定: terraform-state-<PROJECT>）
```

バージョニング有効のバケットを作成し、`TF_STATE_BUCKET` に設定する値を表示します。
何度実行しても安全です（既存バケットは設定の更新のみで、state には触れません）。
state の過去の版はバージョニングで保持され、古い版（新しい版が 5 つ以上ある、または古い版になって 90 日経過）だけが自動削除されます。
誤って壊した場合は `gcloud storage ls -a gs://<bucket>/terraform/` で過去の版を確認して復元できます。

### 2. WIF とデプロイ用サービスアカウントを作成（ローカル・初回とまれな変更のみ）

値はファイルに保存せず、引数で渡します。

```bash
gcloud auth application-default login
cd terraform/bootstrap/prod
terraform init -backend-config="bucket=YOUR_TF_STATE_BUCKET" -backend-config="prefix=terraform/bootstrap"
terraform apply \
  -var="project=YOUR_PROJECT_ID" \
  -var="github_repository=OWNER/REPO"     # このリポジトリ。GitHub 上の名前と完全に一致させる
terraform output -raw wif_provider; echo
terraform output -raw deployer_service_account_email; echo
```

### 3. GitHub リポジトリの設定

[設定項目](#設定項目) の Environment と Variables をすべて設定し、[Secret の登録と更新](#secret-の登録と更新) の手順で Secrets を登録します。
fork の場合は Actions タブからワークフローを有効にしてください（fork では既定で無効）。

### 4. 以降

`main` に push すると `.github/workflows/deploy.yml` が `cloud_function/` を zip にして `terraform/environments/prod` を `terraform apply` します。
初回のアプリのリソース作成も CI で行われます（Actions タブの Deploy から手動実行も可能）。
ソースが変わると GCS 上のオブジェクト名（内容ハッシュ）が変わり、関数が再デプロイされます。
`environments/prod` の変更も同様に push で反映し、ローカルからの plan / apply は行いません。

## Secret の登録と更新

API キーなどは GitHub の Environment `prod` の Secrets を正とし、デプロイ時に Terraform が Secret Manager へ書き込みます（`modules/secret_versions`）。
値は書き込み専用の引数で渡すため、plan と state には残りません。
Terraform は値の変化を比べられないので、**値を変えたら `terraform/environments/prod/main.tf` の `module "secret_versions"` の番号を上げて** マージします。番号が変わった Secret だけ、新しいバージョンが書き込まれます。

1. テンプレートをリポジトリの外にコピーして記入する（認証情報を含むため、リポジトリの中には置かない）

   ```bash
   cp -r secrets.example ~/result-tweet-bot-secrets
   ```

   | ファイル | 内容 |
   | --- | --- |
   | `RIOT_API_KEY.txt` | Riot の API キー（`RGAPI-` で始まる） |
   | `X_APP_CREDENTIALS.json` | X アプリの Consumer Key（画面の表示は API Key）と Consumer Secret（API Key Secret） |
   | `ACCOUNTS.json` | 対象アカウントのセットの配列。`id` は保存先のパスに使うため一度決めたら変えない。`riot.platform` は `jp1` など。`x.access_token` / `x.access_token_secret` は投稿するアカウントのもの（アプリの権限を Read and write にしてから発行する）。`x.root_post_id` はリプライをつなげる固定ポストの ID（文字列） |

2. 検証して登録する（値は表示されない）

   ```bash
   ./scripts/set_secrets.sh --check   # 検証のみ
   ./scripts/set_secrets.sh           # 3 つとも登録（1 つだけなら名前を指定）
   ```

3. `module "secret_versions"` の番号を上げる PR を出してマージする（初回は 1 のままでよい）

Riot の Development キーは 24 時間で失効するため、開発中は毎日次を実行して更新します。GitHub Secret と同時に Secret Manager にも直接書き込むので、PR は不要です（関数は常に最新のバージョンを読む）。

```bash
./scripts/set_secrets.sh --direct RIOT_API_KEY
```

## セキュリティ

- Workload Identity Federation で、`github_repository` の `deploy_branch`（既定 `main`）で動くワークフローだけが認証できます。fork や Pull Request からは認証できません。
- ワークフローは `pull_request` では実行せず、Environment `prod` は `main` ブランチからのみ使用できます。
- デプロイ用サービスアカウントのロールは `roles/editor` と `roles/pubsub.admin`（Cloud Scheduler が topic に publish するための権限付与に必要）のみです。プロジェクトの IAM や WIF は変更できません。
- Secret Manager の Secret に対して、デプロイ用サービスアカウントはバージョンの追加・破棄のみ、関数の実行用サービスアカウントは読み取りのみ可能です。

## ローカルでの動作確認

```bash
cd cloud_function
python -c "import main; print(main.daily_job({}, None))"
```
