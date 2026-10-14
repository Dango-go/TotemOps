include "root" {
    path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/vpc.hcl"
  expose = true
}

inputs = {
    vpc_name = "prod-vpc-2026"
    cidr_block = "10.2.0.0/16"
    availability_zones = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]
    public_subnet_cidrs = [
        "10.2.1.0/24",
        "10.2.2.0/24",
        "10.2.3.0/24"
    ]
    private_subnet_cidrs = [
        "10.2.10.0/24",
        "10.2.20.0/24",
        "10.2.30.0/24"
    ]
    cluster_name = "totemops-prod-eks"
}