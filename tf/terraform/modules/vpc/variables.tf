variable "vpc_name" {
  type        = string
  description = "Name of the VPC"
}

variable "cidr_block" {
  type        = string
  description = "CIDR block for the VPC"
}

variable "availability_zones" {
  type        = list(string)
  description = "Explicit list of availability zones to use. If empty, the first 3 available AZs in the region will be used."
  default     = []
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "List of CIDR blocks for public subnets (e.g. ['10.0.1.0/24', '10.0.2.0/24', '10.0.3.0/24'])"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "List of CIDR blocks for private subnets (e.g. ['10.0.10.0/24', '10.0.20.0/24', '10.0.30.0/24'])"
}

variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster (used for Kubernetes discovery tags on subnets)"
}

variable "single_nat_gateway" {
  type        = bool
  description = "If true, provision a single NAT Gateway shared across all private subnets to save cost (ideal for dev/stage). If false, provision one per AZ for high availability (prod)."
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}
