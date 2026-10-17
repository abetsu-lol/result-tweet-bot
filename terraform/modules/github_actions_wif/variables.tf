variable "project" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "name" {
  description = "デプロイ用サービスアカウント ID の接頭辞（<name>-deployer。全体で 30 文字以内）"
  type        = string
}

variable "github_repository" {
  description = "Workload Identity Federation 経由でのデプロイを許可する GitHub リポジトリ（'owner/repo' 形式）"
  type        = string
}

variable "deploy_branch" {
  description = "Workload Identity Federation での認証を許可する GitHub Actions のブランチ"
  type        = string
  default     = "main"
}

variable "deployer_roles" {
  description = "デプロイ用サービスアカウントに付与するプロジェクトのロール"
  type        = list(string)
}
