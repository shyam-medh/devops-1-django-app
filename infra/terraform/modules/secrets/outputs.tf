output "external_secrets_role_arn" {
  description = "IAM Role ARN for External Secrets Operator"
  value       = module.iam_iam-role-for-service-accounts-eks.iam_role_arn
}
