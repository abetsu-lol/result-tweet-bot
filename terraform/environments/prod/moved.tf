// Resources were defined in the root module before being split into modules.
// These keep the existing state attached to them; they can be removed once applied.

moved {
  from = google_project_service.cloudfunctions
  to   = module.scheduled_function.google_project_service.cloudfunctions
}

moved {
  from = google_project_service.pubsub
  to   = module.scheduled_function.google_project_service.pubsub
}

moved {
  from = google_project_service.scheduler
  to   = module.scheduled_function.google_project_service.scheduler
}

moved {
  from = google_project_service.storage
  to   = module.scheduled_function.google_project_service.storage
}

moved {
  from = google_storage_bucket.function_source_bucket
  to   = module.scheduled_function.google_storage_bucket.function_source_bucket
}

moved {
  from = google_storage_bucket_object.function_zip
  to   = module.scheduled_function.google_storage_bucket_object.function_zip
}

moved {
  from = google_pubsub_topic.daily_topic
  to   = module.scheduled_function.google_pubsub_topic.daily_topic
}

moved {
  from = google_cloudfunctions_function.daily_function
  to   = module.scheduled_function.google_cloudfunctions_function.daily_function
}

moved {
  from = google_pubsub_topic_iam_member.scheduler_publisher
  to   = module.scheduled_function.google_pubsub_topic_iam_member.scheduler_publisher
}

moved {
  from = google_cloud_scheduler_job.daily_trigger
  to   = module.scheduled_function.google_cloud_scheduler_job.daily_trigger
}

moved {
  from = google_project_service.iam
  to   = module.github_actions_wif.google_project_service.iam
}

moved {
  from = google_project_service.iamcredentials
  to   = module.github_actions_wif.google_project_service.iamcredentials
}

moved {
  from = google_project_service.sts
  to   = module.github_actions_wif.google_project_service.sts
}

moved {
  from = google_iam_workload_identity_pool.github_pool
  to   = module.github_actions_wif.google_iam_workload_identity_pool.github_pool
}

moved {
  from = google_iam_workload_identity_pool_provider.github_provider
  to   = module.github_actions_wif.google_iam_workload_identity_pool_provider.github_provider
}

moved {
  from = google_service_account.github_actions_sa
  to   = module.github_actions_wif.google_service_account.github_actions_sa
}

moved {
  from = google_project_iam_member.github_actions_roles
  to   = module.github_actions_wif.google_project_iam_member.github_actions_roles
}

moved {
  from = google_service_account_iam_member.github_binding
  to   = module.github_actions_wif.google_service_account_iam_member.github_binding
}
