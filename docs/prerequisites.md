# Prerequisites

What you need before you start building.

## An AWS account you can create infrastructure in

You create the cluster yourself, in your own account, and you pay for it while it runs.
`provision/` holds the Terraform that builds it. Read
[provision/README.md](../provision/README.md) before you apply anything: it opens with the cost.

The short version is roughly **$0.55 an hour, about $13 a day**, and the NAT gateway keeps
billing whether or not you are using the cluster. Tear down with `./provision/destroy.sh` when
you stop for the day.

You need:

- Permission to create VPC, EKS, IAM and EC2 resources.
- Credentials that resolve for the AWS CLI. `AWS_PROFILE`, SSO, environment variables and
  instance roles all work.
- **A raised vCPU quota.** A new AWS account defaults to 5 running on-demand standard vCPUs and
  one `t3.2xlarge` is 8. Request an increase to "Running On-Demand Standard (A, C, D, H, I, M, R,
  T, Z) instances" before you begin. It can take a day to be granted, and it is the one
  prerequisite you cannot work around on the evening you sit down to start.

## Tools

| Tool | Why |
|---|---|
| Terraform 1.10 or newer | Builds the cluster |
| AWS CLI v2 | Credentials, and reading cluster facts back |
| kubectl | Everything after the cluster exists |
| helm | The ArgoCD bootstrap |
| git | The GitOps loop |
| jq | Used by the provisioning scripts |

## An agentic coding CLI

The platform is built by pointing an agent at `spec/` and letting it work through the phases.
This repository was built and tested entirely with Claude Code, and it is the only tool the
phases are verified against.

Other agentic CLIs may work if they run with a permissioned (non-auto-approve) mode, because
several phases depend on you seeing and approving what the agent is about to do. As of June 2026
these exist and function in principle: OpenAI Codex CLI, GitHub Copilot CLI, Google Antigravity
CLI, Amazon Kiro CLI, opencode, Goose, and Cursor CLI. None are tested here.

If you bring an alternative: avoid Gemini CLI (retired for personal plans) and Amazon Q Developer
CLI (new signups closed). Cursor CLI cannot use the in-cluster model, which matters from the model
serving chapter onward.

You can also read the chapters against `solution/`, which is the finished build, without running
an agent at all.

## Background

Working familiarity with Kubernetes, Helm, and GitOps (Argo CD or Flux experience helps).

No prior Backstage experience required.
