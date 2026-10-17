variable "project" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "roles" {
  description = "Cloud Build が使うサービスアカウント（Compute Engine のデフォルト SA）に付与するプロジェクトのロール"
  type        = list(string)
  default     = ["roles/run.builder"]
}
