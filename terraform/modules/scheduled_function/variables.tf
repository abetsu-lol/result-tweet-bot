variable "project" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "region" {
  description = "関数・ソース用バケット・Scheduler のジョブを置く GCP リージョン"
  type        = string
}

variable "name" {
  description = "関数の名前。関連リソースの名前の接頭辞にも使う"
  type        = string
}

variable "source_dir" {
  description = "関数のソースディレクトリ。source_zip_path に固めた内容と一致している必要がある"
  type        = string
}

variable "source_zip_path" {
  description = "scripts/package_function.sh で作成した関数のソース zip のパス"
  type        = string
}

variable "runtime" {
  description = "Cloud Functions（1st gen）のランタイム"
  type        = string
  default     = "python312"
}

variable "image_keep_count" {
  description = "Artifact Registry に残す関数イメージの数（新しいものから）。それより古いものは削除される"
  type        = number
  default     = 2
}

variable "entry_point" {
  description = "呼び出す関数のソース上の名前"
  type        = string
  default     = "daily_job"
}

variable "schedule" {
  description = "Cloud Scheduler のジョブの cron スケジュール"
  type        = string
  default     = "0 3 * * *"
}

variable "time_zone" {
  description = "スケジュールのタイムゾーン"
  type        = string
  default     = "Asia/Tokyo"
}
