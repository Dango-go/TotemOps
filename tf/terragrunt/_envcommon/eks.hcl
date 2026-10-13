# tf/terragrunt/_envcommon/eks.hcl

terraform {
  source = "${get_repo_root()}/tf/terraform/modules/eks"
}

inputs = {

  cluster_version = "1.30"
}
