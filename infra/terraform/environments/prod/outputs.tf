# output "frontend_s3_bucket" {
#   value = module.s3_frontend.s3_bucket_name
# }

# output "cloudfront_domain_url" {
#   value = module.s3_frontend.cloudfront_domain_name
# }

output "external_secrets_role_arn" {
  value = module.secrets.external_secrets_role_arn
}

# RDS endpoint — used by the deploy script to inject the correct DB_HOST
# into the Django Helm chart via --set, since the endpoint changes on every
# fresh terraform apply and must never be hardcoded in values.yaml.
output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "rds_host" {
  # Strip the :3306 port suffix that AWS appends to the endpoint
  value = split(":", module.rds.db_instance_endpoint)[0]
}
