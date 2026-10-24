// The deployer's binding was renamed when the planner service account was added.
// This moves it in state instead of destroying and recreating it,
// which would briefly break deploys from main.
moved {
  from = google_service_account_iam_member.github_actions
  to   = google_service_account_iam_member.deploy_github_actions
}
