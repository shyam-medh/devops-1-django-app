output "file_system_id" {
  value       = aws_efs_file_system.jenkins.id
  description = "The ID of the EFS file system"
}

output "access_point_id" {
  value       = aws_efs_access_point.jenkins.id
  description = "The ID of the EFS access point for Jenkins"
}
