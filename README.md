# result-tweet-bot

League of Legends の指定したアカウントのランク戦（ソロ / デュオ）の戦績を Riot Games API から取得して保存し、X（旧 Twitter）の固定ポストへのリプライとして毎日投稿するボットと、そのインフラ一式です。

毎日 12:05（JST）に Google Cloud Functions（1st gen、Cloud Scheduler → Pub/Sub で起動）が実行され、前日 12:00〜当日 12:00 に終わった試合を集計して投稿します。

```
cloud_function/   アプリ本体（エントリポイント: daily_job(event, context)）
terraform/
  bootstrap/prod/     CI の前提となるリソース（WIF・デプロイ用 / plan 用 / 関数の実行用サービスアカウント・ビルドの権限・Secret の器・戦績データ用バケット）。ローカルから apply
  environments/prod/  アプリのリソース（Cloud Function・Pub/Sub・Cloud Scheduler・イメージ用 Artifact Registry・Secret の値）。CI から apply
  modules/scheduled_function/  Cloud Function + Pub/Sub + Cloud Scheduler + イメージ用 Artifact Registry（最新 2 件のみ保持）
  modules/secret_versions/     Secret Manager の Secret の値（書き込み専用。plan と state に残らない）
  modules/github_actions_wif/  GitHub Actions 用 Workload Identity Federation とデプロイ用 / plan 用サービスアカウント
  modules/function_build_iam/  関数のビルドに Cloud Build が使うサービスアカウント（Compute Engine のデフォルト SA）の権限
  modules/function_runtime/    関数の実行用サービスアカウント・Secret Manager の Secret（器のみ）・戦績データ用バケットと権限
scripts/
  bootstrap.sh         tfstate 用バケットの作成
  package_function.sh  cloud_function/ を zip にする（デプロイ時に CI が実行）
  set_secrets.sh       API キーなどを検証して GitHub Secrets に登録する
  build_font.py        画像用の日本語フォント（使う文字だけに絞ったもの）を作る
secrets.example/  set_secrets.sh で使う、値を記入するファイルのテンプレート
tests/            テスト（pytest）
.github/workflows/deploy.yml      main への push で terraform/environments/prod を apply し、成功したらタグと Release を作る
.github/workflows/pre_deploy.yml  main 向けの Pull Request でテストと Terraform の fmt / validate / plan を実行
.releaserc.json                   semantic-release の設定（リリースとバージョン）
```

コードには特定の環境の値（プロジェクト ID・バケット名など）を含めていません。値はすべて GitHub リポジトリの設定から渡します。
GitHub Actions は、**ワークフローを実行するリポジトリに設定された Variables の GCP プロジェクト**にデプロイします。
fork（または clone して自分のリポジトリに push）し、以下の手順で設定すれば自分の環境で同じように動かせます。

## 構成の考え方

| | 内容 | apply する場所 | state（tfstate 用バケット内の prefix） |
| --- | --- | --- | --- |
| tfstate 用バケット | `scripts/bootstrap.sh`（gcloud） | ローカル | — |
| `terraform/bootstrap/prod` | WIF プール / プロバイダ、デプロイ用 / plan 用サービスアカウントとその権限、関数のビルドに使うサービスアカウントの権限、関数の実行用サービスアカウント・Secret・戦績データ用バケット | ローカル（初回とまれな変更のみ） | `terraform/bootstrap` |
| `terraform/environments/prod` | Cloud Function・Pub/Sub・Cloud Scheduler・イメージ用 Artifact Registry・Secret の値 | CI | `terraform/state` |

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
| リポジトリの Variable | `GCP_PROJECT_ID` / `GCP_REGION` / `TF_STATE_BUCKET` / `GCP_WORKLOAD_PROVIDER` | Environment `prod` と同じ値 | Pull Request の plan（`pre_deploy.yml`）が参照する。Pull Request の実行は Environment `prod` を使えないため、リポジトリにも置く |
| リポジトリの Variable | `GCP_PLAN_SA_EMAIL` | plan 用サービスアカウントのメールアドレス | `terraform/bootstrap/prod` の `terraform output -raw planner_service_account_email` |

Terraform の変数との対応:

| Terraform 変数 | 値の出どころ |
| --- | --- |
| `environments/prod`: `project` / `region` | `GCP_PROJECT_ID` / `GCP_REGION` |
| `environments/prod`: `riot_api_key` / `x_app_credentials` / `accounts` | Secrets（`TF_VAR_*`）。書き込み専用で Secret Manager に書き込まれ、plan と state には残らない |
| `bootstrap/prod`: `project` / `github_repository` / `tf_state_bucket` | ローカルでの apply 時に `-var` で指定 |
| リソース名（`name`）・スケジュール・デプロイ用ブランチ・デプロイ用サービスアカウントのロールほか | 各ルートの `main.tf` のモジュール引数。変える場合は編集する |

## 自分の環境にデプロイする

前提: GCP プロジェクト（課金有効）、`gcloud`、`gh`、Terraform >= 1.11、Python >= 3.12、GitHub リポジトリ、bash（Windows では Git Bash）。
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

### 2. CI の前提となるリソースを作成（ローカル・初回とまれな変更のみ）

WIF、デプロイ用 / plan 用 / 関数の実行用サービスアカウント、ビルドの権限、Secret の器、戦績データ用バケットを作成します。

値はファイルに保存せず、引数で渡します。

```bash
gcloud auth application-default login
cd terraform/bootstrap/prod
terraform init -backend-config="bucket=YOUR_TF_STATE_BUCKET" -backend-config="prefix=terraform/bootstrap"
terraform apply \
  -var="project=YOUR_PROJECT_ID" \
  -var="github_repository=OWNER/REPO" \   # このリポジトリ。GitHub 上の名前と完全に一致させる
  -var="tf_state_bucket=YOUR_TF_STATE_BUCKET"
terraform output -raw wif_provider; echo
terraform output -raw deployer_service_account_email; echo
terraform output -raw planner_service_account_email; echo
```

### 3. GitHub リポジトリの設定

[設定項目](#設定項目) の Environment と Variables をすべて設定し、[Secret の登録と更新](#secret-の登録と更新) の手順で Secrets を登録します。
fork の場合は Actions タブからワークフローを有効にしてください（fork では既定で無効）。

### 4. 以降

`main` に push すると `.github/workflows/deploy.yml` が `cloud_function/` を zip にして `terraform/environments/prod` を `terraform apply` します。
初回のアプリのリソース作成も CI で行われます（Actions タブの Deploy から手動実行も可能。[手動実行](#手動実行)）。
ソースが変わると GCS 上のオブジェクト名（内容ハッシュ）が変わり、関数が再デプロイされます。
`environments/prod` の変更も同様に push で反映し、ローカルからの plan / apply は行いません。
デプロイが成功すると、そのコミットにバージョンのタグが付きます（[リリースとバージョン](#リリースとバージョン)）。

## 手動実行

Actions タブの Deploy（`workflow_dispatch`）から、その時点の `main` の先頭を push と同じ手順でデプロイできます。
デプロイできるのは `main` から実行したときだけです。
他のブランチやタグから実行すると、`deploy` ジョブは Environment `prod` のブランチ制限に拒否されて失敗します（ステップは 1 つも実行されず、Secrets も渡らない。`release` もスキップされ、タグは付かない）。
手動実行は実行元に選んだブランチやタグにある `deploy.yml` で動くため、ワークフローを書き換えたブランチからでも同じです（GCP 側でも WIF が `main` 以外を拒否する。[セキュリティ](#セキュリティ)）。

| 場面 | 手段 |
| --- | --- |
| 初回のアプリのリソース作成（bootstrap の後、まだ push していないとき） | 手動実行 |
| コンソールなどで手で変えたリソースを `main` の状態に戻す | 手動実行 |
| fork で `DEPLOY_ENABLED` を設定した直後 | 手動実行 |
| 一時的な失敗のやり直し | 失敗した実行の Re-run jobs（同じコミットで再実行する。手動実行はその時点の `main` の先頭を使う） |
| Secret の値の更新 | 番号を上げる PR（[Secret の登録と更新](#secret-の登録と更新)）。手動実行しても新しいバージョンは書き込まれない |
| 以前のバージョンに戻す | revert のコミットを `main` に push する。タグからの手動実行は失敗する（上記） |

- push による実行と同じ `concurrency` グループで動きます。実行中のデプロイがあれば終わるまで待ちますが、待てるのは 1 件だけで、さらに次の実行が入ると先に待っていたほうはキャンセルされます。後の実行が `main` からなら最新の `main` を含むため変更は漏れませんが、`main` 以外からの実行が入ると、待っていた `main` の実行がキャンセルされたまま、次の push か手動実行までデプロイされません。
- 前回のリリース以降にリリース対象のコミット（`feat:` / `fix:` など。[リリースとバージョン](#リリースとバージョン)）がなければ `terraform apply` だけが行われ、リリースは作られません。前回のデプロイが失敗してリリースされていないコミットがあれば、まとめてリリースされます。

## リリースとバージョン

[semantic-release](https://semantic-release.gitbook.io/) が `main` のコミットメッセージからバージョンを決め、デプロイしたコミットにタグ（`vX.Y.Z`）と GitHub Release を作ります。

| コミットの種類（[Conventional Commits](https://www.conventionalcommits.org/ja/)） | バージョン |
| --- | --- |
| `feat!:` など `!` 付き、または本文に `BREAKING CHANGE:` | メジャー（1.0.0 → 2.0.0） |
| `feat:` | マイナー（1.0.0 → 1.1.0） |
| `fix:` / `perf:` | パッチ（1.0.0 → 1.0.1） |
| それ以外（`ci:` / `chore:` / `docs:` / `refactor:` / `test:` など） | リリースしない（デプロイはする） |

- Pull Request は squash merge するため、**PR のタイトル**（コミットが 1 つの PR ではそのコミットのメッセージ）を上の形式にします。
- 最初のリリースは `v1.0.0` です。
- `deploy.yml` は次の 3 つのジョブで動きます。デプロイに失敗したコミットにはタグが付きません。

  | ジョブ | 内容 |
  | --- | --- |
  | `version` | 次のバージョンを計算する（dry-run。タグは作らない） |
  | `deploy` | `version` が成功し、`DEPLOY_ENABLED` が `true` のときに `terraform apply` する（`main` 以外からの実行は Environment `prod` に拒否される） |
  | `release` | `deploy` が成功したら、そのコミットにタグと Release を作り、`version` で計算したバージョンと一致するかを確認する |

- 実行中に `main` へ次の push が入ると、`release` はリリースを見送り（警告のみ）、次の実行がまとめてリリースします。
- 設定は `.releaserc.json` にあります。semantic-release と conventionalcommits プリセットのバージョンは `deploy.yml` の `env` で固定しています。Dependabot では更新されないため、手で上げます。

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

3. `module "secret_versions"` の番号を上げる PR を出してマージする（初回は番号を変えなくてよい）

Personal / Production キーは失効しないため、上の手順（番号を上げる PR）で更新します。
Riot の Development キーは 24 時間で失効するため、Development キーで開発している間は毎日次を実行して更新します。GitHub Secret と同時に Secret Manager にも直接書き込むので、PR は不要です（関数は常に最新のバージョンを読む）。

```bash
./scripts/set_secrets.sh --direct RIOT_API_KEY
```

## Riot Games API の使い方

開発中は Development キー、公開後は Personal キーで運用します。

| API | エンドポイント | 用途 | 呼び出し |
| --- | --- | --- | --- |
| ACCOUNT-V1 | `GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}` | Riot ID から PUUID を取得 | 1 日 1 回（PUUID は API キーごとに暗号化された値なので保存しない） |
| MATCH-V5 | `GET /lol/match/v5/matches/by-puuid/{puuid}/ids`（`queue=420`、`startTime` / `endTime` 指定） | 前回の続きから終わった試合の ID を取得 | 1 日 1 回（100 件ごとにページ分け） |
| MATCH-V5 | `GET /lol/match/v5/matches/{matchId}` | 試合の詳細 | 一覧で得た試合ごとに 1 回（一覧は開始時刻で絞り込むため、2 時間前に始まった試合も取得し、終了時刻で選び直す） |
| MATCH-V5 | `GET /lol/match/v5/matches/{matchId}/timeline` | 15 分時点の指標の計算 | 15 分以上の試合ごとに 1 回 |
| LEAGUE-V4 | `GET /lol/league/v4/entries/by-puuid/{puuid}` | 区切りの時点のソロ / デュオのランクと LP（投稿の本文に表示） | 1 日 1 回 |

- ACCOUNT-V1 / MATCH-V5 はアカウントのサーバー（`platform`）から決まる地域（日本は `asia`）、LEAGUE-V4 はサーバー（日本は `jp1`）にルーティングします。
- 1 アカウントあたりの呼び出しは、1 日に「約 2 × 試合数 + 3 回」です（1 日 10 試合なら約 23 回）。Development / Personal キーのレート制限（20 回 / 秒、100 回 / 2 分）の範囲に収まります。
- 429（レート制限）は `Retry-After` に従って待ってから再試行し、5xx は間隔を空けて再試行します。
- すべてのリクエストに `User-Agent: result-tweet-bot/0.1 (+<リポジトリの URL>)` を付けます（`bot/http.py` の固定値。リリースのタグとは連動しない）。
- API キーは Secret Manager に保存し、実行時に読み込みます（コードやログには含めない）。
- チャンピオンの日本語名とアイコンは Data Dragon（`ddragon.leagueoflegends.com`、API キー不要）から取得します。

## セキュリティ

- Workload Identity Federation で認証できるのは `github_repository` のワークフローだけで、使えるサービスアカウントは実行の種類で分かれます。
  - デプロイ用サービスアカウントを使えるのは `deploy_branch`（既定 `main`）で動く実行のみです。
  - Pull Request（`pull_request` イベント）の実行が使えるのは、`terraform plan` 用の読み取り専用サービスアカウント（`roles/viewer` と tfstate 用バケットの読み取りのみ）だけです。WIF 側ではマージ先のブランチを制限しておらず、`main` 向けに限っているのはワークフロー（`pre_deploy.yml`）のトリガーです。
  - fork からの Pull Request には GitHub が OIDC トークンを発行しないため認証できません。`pull_request_target` も拒否します。
- ワークフローは `pull_request` では実行せず、Environment `prod` は `main` ブランチからのみ使用できます。
- デプロイ用サービスアカウントのロールは `roles/editor` と `roles/pubsub.admin`（Cloud Scheduler が topic に publish するための権限付与に必要）のみです。プロジェクトの IAM や WIF は変更できません。
- Secret Manager の Secret に対して、デプロイ用サービスアカウントはバージョンの追加・破棄のみ、関数の実行用サービスアカウントは読み取りのみ可能です。

## アプリの構成

`cloud_function/` が関数のソースです（`scripts/package_function.sh` で zip にしてデプロイされる）。

| ファイル | 役割 |
| --- | --- |
| `main.py` | エントリポイント `daily_job(event, context)` |
| `bot/app.py` | 1 回の実行。アカウントごとに収集 → 投稿し、1 つの失敗で他を止めない |
| `bot/collect.py` | 前回の続きから、終了時刻が 12:00〜12:00（JST）に入るソロ / デュオ（queue 420）の試合を取得し、元データと指標を保存する（15 分未満の試合は除外） |
| `bot/metrics.py` | 試合ごとの指標。`@metric("名前")` を付けた関数を追加すると、以後の試合に保存される |
| `bot/publish.py` | 投稿するか（`POST_SCHEDULE`）と対象期間を決め、保存済みの指標から投稿を組み立てて固定ポストのリプライツリーに投稿する。`DRY_RUN` では投稿せず `previews/` に保存 |
| `bot/render.py` / `bot/aggregate.py` / `bot/text.py` | 表の画像（試合ごと / チャンピオン別）、本文、X の文字数の数え方（日本語は 2）。試合ごとの表のレーンのアイコンは Pillow で描いた自作のもの（Riot の素材は使っていない） |
| `bot/ddragon.py` | チャンピオンの日本語名とアイコン（Data Dragon） |
| `bot/x.py` | X API（OAuth 1.0a、画像のアップロード、リプライ）。投稿は再試行しない |
| `bot/period.py` | 日の区切り（12:00 JST。日付は区切りの開始日） |
| `bot/riot.py` / `bot/gcp.py` / `bot/http.py` | Riot API、Secret Manager / GCS（REST）、HTTP の共通処理（User-Agent、429 / 5xx の再試行） |
| `bot/config.py` | 環境変数と `ACCOUNTS` の読み込み・検証 |

戦績データ用バケットの中身:

| パス | 内容 |
| --- | --- |
| `raw/matches/<match id>.json.gz` | 試合の詳細とタイムライン（gzip）。試合ごとに 1 回だけ書き込む |
| `metrics/<account id>/<日付>.ndjson` | その日の試合の指標（1 行 1 試合）。`participant_id` で元データの中の自分を特定できる |
| `ranks/<account id>/<日付>.json` | その日の 12:00 の区切りの直後に取得したソロ / デュオのランク（投稿の本文に表示）。取得に失敗した日はファイルがなく、本文のランクの行が省かれる |
| `state/<account id>.json` | 収集・投稿の進み具合（`last_collected_end` / `last_post_end` / `last_post_id`）。PUUID は API キーごとに暗号化された値なので保存せず、実行のたびに取得する |
| `previews/<account id>/<日付>/` | `DRY_RUN` のときに作った投稿の本文と画像 |

投稿の設定（`terraform/environments/prod/main.tf` の関数の環境変数）:

| 環境変数 | 値 | 内容 |
| --- | --- | --- |
| `POST_SCHEDULE` | `daily` / `weekly:MON`〜`weekly:SUN` | 毎日投稿するか、指定した曜日（JST）だけ投稿するか。対象期間は前回の投稿の区切りから今回の区切りまで（最長 7 日）なので、切り替えても試合が抜けたり重複したりしない |
| `POST_FORMAT` | `image` / `text` | 表の画像付きか、テキストのみ。画像は必ず 1 投稿（4 枚まで）に収める（1 枚 8 行を基本に、足りなければ 1 枚 25 行まで増やす。100 試合を超えたら直近 100 試合を載せる）。テキストは 280 文字を超えると複数のリプライに分ける |
| `POST_LAYOUT` | `per_game` / `summary` | 試合ごとの一覧か、チャンピオン別の集計か |
| `DRY_RUN` | `true` / `false` | `false` 以外では投稿しない |

画像の日本語フォントは Noto Sans JP（SIL Open Font License 1.1、`cloud_function/bot/assets/OFL.txt`）を、使う文字だけに絞って同梱しています。新しいチャンピオンが追加されたら `.venv/Scripts/python scripts/build_font.py` で作り直します（日本語名にフォントにない文字があると、その文字が表示されないため）。

## テスト

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS / Linux: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/python -m coverage run --branch --source=cloud_function -m pytest && .venv/Scripts/python -m coverage report -m
.venv/Scripts/python -m pip_audit -r cloud_function/requirements.txt   # 依存ライブラリの既知の脆弱性
```

Riot API・GCS・Secret Manager は偽物に差し替えて実行します（通信しない）。
`main` 向けの Pull Request では、`pre_deploy.yml` が pytest と Terraform の fmt / validate / plan（`environments/prod`、plan 用サービスアカウントで `-lock=false`）を実行します。

依存ライブラリは `==` で固定し（デプロイのたびに中身が変わらないようにするため）、固定した時点の最新版を選んでいます。以後の更新は Dependabot の PR で行います。

## ライセンス・免責事項

MIT License（[LICENSE](LICENSE)）。画像に同梱しているフォントは SIL Open Font License 1.1（`cloud_function/bot/assets/OFL.txt`）。

result-tweet-bot isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

（result-tweet-bot は Riot Games が承認したものではなく、Riot Games および Riot Games の資産の制作・管理に公式に関わる人の見解や意見を反映するものではありません。Riot Games および関連するすべての資産は、Riot Games, Inc. の商標または登録商標です。）
