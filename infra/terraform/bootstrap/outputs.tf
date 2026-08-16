output "terraform_state_bucket" {
  value = aws_s3_bucket.terraform_state.bucket
}

output "terraform_state_dynamodb_table" {
  value = aws_dynamodb_table.terraform_state_lock.name
}
