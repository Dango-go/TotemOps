# tf/terragrunt/root.hcl

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket       = "totemops-tf-state-2026"
    key          = "${path_relative_to_include()}/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
    profile      = "totemops" # <--- НАЗВА ТВОГО ПРОФІЛЮ З AWS CLI
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region  = "eu-central-1"
  profile = "main" 

  default_tags {
    tags = {
      Project   = "TotemOps"
      ManagedBy = "Terragrunt"
    }
  }
}
EOF
}
