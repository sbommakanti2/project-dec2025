// Handy outputs so reviewers can quickly grab ALB + ECR details.
output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer"
  value       = aws_lb.app.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository to push the API image"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_id" {
  description = "ECS cluster identifier"
  value       = aws_ecs_cluster.app.id
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.app.name
}
