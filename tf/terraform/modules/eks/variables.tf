variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster"
}

variable "cluster_version" {
  type        = string
  description = "Kubernetes version for the EKS cluster"
  default     = "1.30"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the cluster and security groups will be created"
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs for the EKS control plane and worker nodes"
}

# mgnt cluster - t3.large. stage - t3.medium (with SPOT) prod - m6i.large (ON_DEMAND)
variable "node_instance_types" {
  type        = list(string)
  description = "List of EC2 instance types for the managed node group"
  default     = ["t3.medium"]
}

variable "capacity_type" {
  type        = string
  description = "Capacity type for the managed node group: ON_DEMAND or SPOT"
  default     = "ON_DEMAND"
}

variable "min_size" {
  type        = number
  description = "Minimum number of worker nodes"
  default     = 1
}

variable "max_size" {
  type        = number
  description = "Maximum number of worker nodes"
  default     = 5
}

variable "desired_size" {
  type        = number
  description = "Desired number of worker nodes"
  default     = 2
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}
