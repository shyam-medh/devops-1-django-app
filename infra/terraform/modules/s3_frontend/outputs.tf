output "s3_bucket_name" {
  value       = aws_s3_bucket.frontend.bucket
  description = "Name of the S3 bucket"
}

output "website_endpoint" {
  description = "The S3 static website endpoint"
  value       = aws_s3_bucket_website_configuration.frontend.website_endpoint
}
