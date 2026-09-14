# Provisioning the cluster

One EKS cluster for building the platform. Terraform creates the VPC, the cluster, a single
node group, the add-ons the platform depends on, and the two EKS Pod Identity associations
that give the AWS Load Balancer Controller and the EBS CSI driver their credentials.

Read the cost section before you run anything.

## What this costs

Approximate, us-west-2 on-demand, as of September 2026. Check the
[AWS pricing calculator](https://calculator.aws/) for current rates in your region.

| Line item | Rate | Per day |
|---|---|---|
| EKS control plane | $0.10/hr | $2.40 |
| 1 x t3.2xlarge node | ~$0.333/hr | ~$8.00 |
| NAT gateway | $0.045/hr plus $0.045/GB | ~$1.08 plus data |
| 50 GB gp3 root volume | ~$0.006/hr | ~$0.13 |
| Platform PVCs (~60 GB) | ~$0.007/hr | ~$0.16 |
| One network load balancer | ~$0.023/hr | ~$0.55 |

**Roughly $0.55 an hour. About $13 a day. About $400 a month if you leave it running.**

The NAT gateway is the one that surprises people. It bills about $32 a month before a single
byte moves, it bills while the cluster sits idle overnight, and it keeps billing if you delete
the node group but leave the VPC. Only `terraform destroy` removes it. Stopping the node or
scaling it to zero does not. The first platform build also pulls roughly 30 GB of container
images through it, a one-time charge of about $1.35.

Set an AWS Budget alarm before you start. Be aware that Budgets data lags 8 to 24 hours, so it
is a smoke alarm rather than a circuit breaker. The circuit breaker is `./provision/destroy.sh`.

## Before you start

- An AWS account you can create VPC, EKS, IAM and EC2 resources in.
- Credentials that resolve for the AWS CLI. `AWS_PROFILE`, SSO, environment variables and
  instance roles all work; this module does not set a profile.
- Terraform 1.10 or newer, AWS CLI v2, kubectl, helm, git, jq.
- **Service quota.** A new AWS account defaults to 5 running on-demand standard vCPUs. One
  t3.2xlarge is 8. Raise "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances"
  before you begin, because the increase can take a day to be granted.

## Provision

```bash
aws sts get-caller-identity                       # confirm which account you are in
cp provision/terraform.tfvars.example provision/terraform.tfvars
terraform -chdir=provision init
terraform -chdir=provision apply                  # about 15 minutes
```

Then point kubectl at it and export what the tests read:

```bash
$(terraform -chdir=provision output -raw update_kubeconfig)
export KUBECONFIG_FILE="$HOME/.kube/config"
export EXPECTED_CONTEXT="$(terraform -chdir=provision output -raw cluster_name)"
```

Confirm the node came up with the raised pod ceiling. This should print `110`, not `58`:

```bash
kubectl get node -o jsonpath='{.items[0].status.allocatable.pods}'
```

At `58` the platform will not fit and roughly fifteen pods stay Pending. That means prefix
delegation did not take effect; re-check the `vpc-cni` add-on configuration before building.

## Keep the state file

`terraform.tfstate` is gitignored, and it is the only thing that can cleanly destroy what was
created. Keep it. If you lose it, tear down by filtering the AWS console on the resource group
this module creates, whose name is the `resource_group` output.

## Tear down

```bash
./provision/destroy.sh
```

Order matters. In-cluster controllers create load balancers and EBS volumes that Terraform does
not own, so `terraform destroy` on its own either hangs waiting for network interfaces or
succeeds and leaves billing resources behind. The script deletes the ArgoCD Applications and the
PVCs first, waits for AWS to release them, then destroys, then sweeps by tag and reports
anything it found rather than deleting silently.
