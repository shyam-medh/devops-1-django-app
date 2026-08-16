output "s3_bucket_name" {
  value       = aws_s3_bucket.frontend.bucket
  description = "Name of the S3 bucket"
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.frontend_distribution.domain_name
  description = "The CloudFront Domain Name for the frontend"
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.frontend_distribution.id
  description = "The CloudFront Distribution ID (useful for Jenkins cache invalidation)"
}
