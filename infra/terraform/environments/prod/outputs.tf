output "frontend_s3_bucket" {
  value = module.s3_frontend.s3_bucket_name
}

output "cloudfront_domain_url" {
  value = module.s3_frontend.cloudfront_domain_name
}
