variable "project" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "github_repository" {
  description = "Workload Identity Federation 経由でのデプロイを許可する GitHub リポジトリ（'owner/repo' 形式）"
  type        = string
}
