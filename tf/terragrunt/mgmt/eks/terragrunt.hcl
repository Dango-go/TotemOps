include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/eks.hcl"
  expose = true
}

dependency "vpc" {
  config_path = "../vpc" # path to mgmt vpc 

   
  mock_outputs = {
    vpc_id          = "vpc-fake-id-for-plan"
    private_subnets = ["subnet-fake-1", "subnet-fake-2", "subnet-fake-3"]
  }
}

inputs = {
  cluster_name = "totemops-mgmt-eks"

 
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnets

 
  node_instance_types = ["t3.medium"]
  capacity_type       = "ON_DEMAND"
  min_size            = 2
  desired_size        = 2
  max_size            = 4

  tags = {
    Environment = "mgmt"
    Role        = "control-plane"
  }
}
