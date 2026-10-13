# tf/terragrunt/_envcommon/vpc.hcl

terraform {
  source = "${get_repo_root()}/tf/terraform/modules/vpc"
}

inputs = {
  # For prod - false.
  single_nat_gateway = true
}
