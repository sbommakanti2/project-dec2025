variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "app_name" {
  description = "Base name for AWS resources"
  type        = string
  default     = "takehome-challenge-crud-api"
}

variable "container_port" {
  description = "Container port exposed by the FastAPI service"
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Number of ECS tasks"
  type        = number
  default     = 1
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}
