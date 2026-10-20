// Supplied by CI from GitHub environment variables (see README)

variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

// Secret values, supplied by CI from GitHub secrets as TF_VAR_*. They have no default on purpose:
// a missing value fails instead of writing a placeholder into Secret Manager.

variable "riot_api_key" {
  description = "Riot Games API key (GitHub secret RIOT_API_KEY)"
  type        = string
  ephemeral   = true
  sensitive   = true

  validation {
    condition     = length(var.riot_api_key) > 0
    error_message = "riot_api_key is empty; set TF_VAR_riot_api_key."
  }
}

variable "x_app_credentials" {
  description = "X app consumer key and secret as JSON (GitHub secret X_APP_CREDENTIALS)"
  type        = string
  ephemeral   = true
  sensitive   = true

  validation {
    condition     = can(jsondecode(var.x_app_credentials))
    error_message = "x_app_credentials is empty or not valid JSON; set TF_VAR_x_app_credentials."
  }
}

variable "accounts" {
  description = "Riot / X account sets as a JSON array (GitHub secret ACCOUNTS)"
  type        = string
  ephemeral   = true
  sensitive   = true

  validation {
    condition     = can(length(jsondecode(var.accounts)))
    error_message = "accounts is empty or not a valid JSON array; set TF_VAR_accounts."
  }
}
