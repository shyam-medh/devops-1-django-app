output "repository_url_django" {
  value = module.ecr_django.repository_url
}

output "repository_url_nginx" {
  value = module.ecr_nginx.repository_url
}
