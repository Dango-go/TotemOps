variable "key_name" {
  type        = string
  description = "Name of the KMS key"
}

variable "description" {
  type        = string
  description = "Description of the KMS key"
  default     = "KMS key for encryption"
}