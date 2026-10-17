// CI が GitHub の Environment の Variables から渡す（README 参照）

variable "project" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "region" {
  description = "GCP リージョン"
  type        = string
}
