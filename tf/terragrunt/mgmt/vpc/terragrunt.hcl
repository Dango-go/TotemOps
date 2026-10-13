include "root" {
    path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/vpc.hcl"
  expose = true
}

inputs = {
    vpc_name = "mgmt-vpc-2026"
    cidr_block = "10.0.0.0/16"
    availability_zones = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]
    public_subnet_cidrs = [
        "10.0.1.0/24",
        "10.0.2.0/24",
        "10.0.3.0/24"
    ]
    private_subnet_cidrs = [
        "10.0.10.0/24",
        "10.0.20.0/24",
        "10.0.30.0/24"
    ]
    cluster_name = "totemops-mgmt-eks"
}