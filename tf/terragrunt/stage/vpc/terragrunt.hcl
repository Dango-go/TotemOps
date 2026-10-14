include "root" {
    path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/vpc.hcl"
  expose = true
}

inputs = {
    vpc_name = "stage-vpc-2026"
    cidr_block = "10.1.0.0/16"
    availability_zones = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]
    public_subnet_cidrs = [
        "10.1.1.0/24",
        "10.1.2.0/24",
        "10.1.3.0/24"
    ]
    private_subnet_cidrs = [
        "10.1.10.0/24",
        "10.1.20.0/24",
        "10.1.30.0/24"
    ]
    cluster_name = "totemops-stage-eks"
}