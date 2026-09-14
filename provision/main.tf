# ABOUTME: Terraform for the single EKS cluster this book's platform is built on.
# ABOUTME: One t3.2xlarge, one NAT gateway, EKS Pod Identity. Apply, build, destroy.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
  # Every taggable resource carries Workshop=packt. The gp3 StorageClass tags the volumes
  # the EBS CSI driver provisions the same way, so one tag filter finds the whole footprint
  # at teardown, including the resources Terraform does not own. Clean up by this tag,
  # never by guessing.
  default_tags {
    tags = {
      Workshop  = "packt"
      Project   = "packt-agentic-devops"
      Purpose   = "agentic-devops-book"
      ManagedBy = "terraform"
      Ephemeral = "true"
    }
  }
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "name" {
  type = string
  # Becomes the cluster name, the prefix of the two IAM roles below, and the value
  # substituted into the AWS Load Balancer Controller manifest by provision/cluster-facts.sh.
  default = "agentic-devops"
}

variable "endpoint_public_access_cidrs" {
  type = list(string)
  # The Kubernetes API endpoint is public so you can reach it from your workstation. It
  # still requires authentication, but narrowing this to your own address is worth the one
  # line if the cluster will live longer than a sitting.
  default = ["0.0.0.0/0"]
}

variable "kubernetes_version" {
  type = string
  # The floor is 1.34, asserted by tests/test_phase_0_preflight.py (MIN_MINOR). 1.35 is what
  # the book builds against and what docs/architecture.md and components.yaml name. Any minor
  # at or above the floor that EKS still offers will work. Check the current EKS support
  # window before raising this, and do not turn it into an allow-list.
  default = "1.35"
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = local.azs
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  # Lean: one NAT gateway shared across AZs, not one per AZ.
  enable_nat_gateway = true
  single_nat_gateway = true

  # Tags the AWS Load Balancer Controller and EKS expect for subnet discovery.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  # Reachable from your workstation for bootstrap and for the tests.
  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs

  # Whoever runs terraform apply gets cluster admin through an EKS access entry, so kubectl
  # works as soon as you run the update_kubeconfig command this module outputs.
  enable_cluster_creator_admin_permissions = true

  # Pod Identity is the AWS-suggested default over IRSA; every workload here (EBS CSI, LB
  # controller) uses it, so no OIDC provider is created. See docs/reference/decisions.md, D16.
  enable_irsa = false

  # Do not let the module manage the control-plane CloudWatch log group. EKS auto-creates
  # /aws/eks/<name>/cluster, and it survives destroy, so a module-managed group collides
  # with "already exists" on any re-provision that reuses the cluster name. Letting EKS
  # own it makes provision idempotent across destroy/apply cycles.
  create_cloudwatch_log_group = false

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  addons = {
    # vpc-cni and kube-proxy must exist before nodes join. Without before_compute
    # the node group is created first, nodes boot with no CNI, stay NotReady, and
    # the group fails with NodeCreationFailure: Unhealthy nodes.
    # Prefix delegation is the reason the whole platform fits on one t3.2xlarge. The
    # default VPC CNI allocates one IP per ENI slot, capping t3.2xlarge at 58 pods; the
    # full platform (kagent alone runs ~8 agents) needs ~75 and the extras go Pending.
    # Prefix delegation assigns /28 prefixes, raising the ceiling to ~110. Set before
    # compute so the node calculates the higher max-pods at boot. Pairs with the node
    # group cloudinit maxPods below.
    vpc-cni = {
      before_compute = true
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    kube-proxy = {
      before_compute = true
    }
    # coredns runs on the nodes, so it installs after the node group exists.
    coredns = {}
    # Pod Identity agent, plus the EBS CSI driver on a Pod Identity association. EKS ships
    # no default StorageClass since 1.30; without this driver and the gp3 class,
    # observability PVCs (Prometheus, Loki) hang Pending.
    eks-pod-identity-agent = {}
    aws-ebs-csi-driver = {
      # Pod Identity association wired into the addon so EKS creates it as part of the addon
      # lifecycle. Ordering-safe: no window where the controller starts without credentials.
      pod_identity_association = [{
        role_arn        = module.ebs_csi_pod_identity.iam_role_arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  eks_managed_node_groups = {
    # One t3.2xlarge. The full platform is roughly 75 pods and fits a single node once
    # prefix delegation is on (see below). t3.2xlarge is the T3 ceiling and the only T3
    # size that fits CPU vLLM.
    # x86 AMI because the vLLM image is vllm-openai-cpu:*-x86_64.
    #
    # Root disk sized to measured need. The full platform pulls ~30 GB of container images
    # (the baked vLLM image dominates) and writes only a few hundred MB to pod layers, for
    # ~35 GB used. 50 GB keeps imagefs usage at ~69%, below kubelet's 85% image-GC high
    # threshold (so the baked vLLM image is never garbage-collected mid-build) and well
    # above the 10% hard-eviction floor. 40 GB would sit at 86%, above the GC threshold; 80+
    # is unjustified over-provisioning.
    #
    # disk_size is deliberately NOT set: terraform-aws-modules/eks manages a launch template
    # for this node group, and disk_size is silently ignored when a launch template exists
    # (a bare disk_size left the root volume at the AMI default 20 GB). block_device_mappings
    # is the launch-template path that actually sizes the root volume. Do not re-add disk_size.
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.2xlarge"]
      min_size       = 1
      max_size       = 1
      desired_size   = 1
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 50
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }
      # AL2023 nodeadm sets max-pods from a static per-instance map that ignores prefix
      # delegation, so raise it explicitly to the prefix-delegation value for t3.2xlarge
      # (110). Without this the node still caps at 58 even with prefix delegation on, and
      # roughly 15 platform pods stay Pending. Verify after apply:
      #   kubectl get node -o jsonpath='{.items[0].status.allocatable.pods}'   # prints 110
      cloudinit_pre_nodeadm = [{
        content_type = "application/node.eks.aws"
        content      = <<-EOT
          apiVersion: node.eks.aws/v1alpha1
          kind: NodeConfig
          spec:
            kubelet:
              config:
                maxPods: 110
        EOT
      }]
    }
  }
}

# Pod Identity role + policy for the EBS CSI driver (AWS-suggested default over IRSA as of
# 2026-07; EBS CSI supports Pod Identity). Role and policy only: associations stays empty
# because the addon block above creates the association via pod_identity_association, which
# keeps EKS in charge of the ordering.
module "ebs_csi_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name                      = "${var.name}-ebs-csi"
  attach_aws_ebs_csi_policy = true

  associations = {}
}

# Pod Identity for the AWS Load Balancer Controller (docs/architecture.md: Pod Identity, not IRSA).
# Without this the controller is Degraded and no ingress/LB reconciles. The Helm chart
# creates the aws-load-balancer-controller SA in kube-system; this binds it to a role
# carrying the LB controller policy.
module "aws_lb_controller_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name                            = "${var.name}-aws-lbc"
  attach_aws_lb_controller_policy = true

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller"
    }
  }
}

# Tracking beyond the state file: a tag-based Resource Group so the AWS console lists
# every Workshop=packt resource live, independent of who ran Terraform. Clean up the
# whole footprint by filtering on this group / tag.
resource "aws_resourcegroups_group" "packt" {
  # Named for the cluster, because resource group names are unique per account and a second
  # cluster would otherwise collide.
  name = var.name
  # AWS allows only [\sa-zA-Z0-9_.-] here: no parentheses, no equals sign.
  description = "All resources for the Agentic DevOps platform build. Tag Workshop is packt."
  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters          = [{ Key = "Workshop", Values = ["packt"] }]
    })
  }
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "resource_group" {
  value = aws_resourcegroups_group.packt.name
}

output "region" {
  value = var.region
}

# The three facts provision/cluster-facts.sh substitutes into the AWS Load Balancer
# Controller manifest. vpc_id is here so nothing has to call describe-cluster for a value
# Terraform already knows.
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "update_kubeconfig" {
  value = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}
