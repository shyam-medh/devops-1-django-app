output "file_system_id" {
  value       = aws_efs_file_system.jenkins.id
  description = "The ID of the EFS file system"
}
