# Decisions

Locked decisions, newest at the bottom. These are the source of truth when a document and reality disagree.

**This is a dated log, and its language is of its time.** The platform was first built to be delivered
to a room of people at once, so entries reason about many clusters where you will run one. That framing
is left in place where it carries the argument, because the reasoning is what makes an entry worth
keeping: "one scoped IAM role reused across clusters rather than a per-cluster OIDC trust policy each"
is a useful argument whether you are running three hundred clusters or one. Entries that recorded only
the logistics of that delivery have been dropped, because they say nothing about the platform.

For the current shape of the platform rather than how it was reached, read [`../architecture.md`](../architecture.md). Entries that name files no longer in this repository are history, not instructions; [`../what-is-not-included.md`](../what-is-not-included.md) says what was removed and why.

Change control: the architecture is locked. Before changing any decision here or in `docs/architecture.md`, read the current state first and understand why it is what it is. A change lands as a new numbered entry that names and supersedes the prior one, with the date and the reason. Never silently overwrite a settled decision.

## D1. Backbone: Amazon EKS, one cluster per student

EKS, one cluster per student, provisioned live. Managed control plane plus a T3 node group. vcluster is not used. Kubernetes 1.35. (June 17, 2026)

## D2. Component set is not a target number

Build the right set of IDP components. The count is whatever it adds up to. CI checks that every entry is version-pinned, not that there are N of them. (June 17, 2026)

## D3. vLLM stays on T3

The in-cluster model runs on t3.2xlarge with the model pre-warmed and a pre-warmed-request fallback. T3 is the last Intel x86 burstable family; the vLLM CPU image is x86. No dedicated compute node. (June 17, 2026)

## D4. Cluster lifetime

Warm before 11:00 AM EDT, torn down about 2 hours after close. No take-home persistence; the repo is the take-home. (June 17, 2026)

## D5. Demo agent model routing

Clusters route the in-cluster agents to the in-cluster vLLM over an OpenAI-compatible endpoint. No external API spend, no external credentials. (June 18, 2026)

## D6. Live build scope: bare cluster, students build everything

The only thing pre-staged is a bare cluster, up, with credentials handed to the student at the start. ArgoCD is not installed, the repo is not cloned, nothing is synced. Your own agentic CLI, driven by the spec document, builds everything from Phase 0, including installing ArgoCD and cloning the repo. Nothing is compiled from source live; the build deploys pre-built images via GitOps, which is why it is fast. (June 19, 2026)

## D7. Pacing: the spec forces stops between phases

The spec document forces a stop between each phase, so you review what the agent did before it moves on. The gates are in the spec itself rather than in any external enforcement. (June 19, 2026)

## D8. Phase structure

Roughly nine phases, Phase 0 through Phase 8. The breakdown is proposed in the spec and settled there. (June 19, 2026)

## D9. Cluster provisioning sits outside the in-cluster build

The cluster, its t3.2xlarge sizing and its add-ons are created before Phase 0 and are not part of what
the agent builds. See [`../../provision/README.md`](../../provision/README.md). Each cluster runs its
own small in-cluster vLLM rather than reaching a large external model, so there is no external API
spend and no external credential anywhere in the build. (June 19, 2026)

## D10. Prerequisite: bring your own agentic CLI

Students bring their own paid agentic coding CLI plan, Claude Code or an equivalent. The workshop does not provide it. The tool must be able to register and run inside the remote cluster system the student is given. (June 19, 2026)

## D11. AI-plane policies precede the AI plane

The AI-plane Kyverno policies are defined in audit mode in Phase 4, as the AI gateway plane lands, so kagent and agentgateway are governed from birth. Phase 8 flips them from audit to enforce and runs the live denial demo. Governance precedes the workload. (June 19, 2026)

## D13. Accepted agentic CLIs; the two LLM roles are distinct

Per-vendor spikes (June 19, 2026) verified which CLIs actually work for the workshop (headless in the remote shell, governed gate, lifecycle hooks for audit). Working set:

- Claude Code (primary): paid plan, OpenAI-compatible base URL works, PreToolUse/PostToolUse hooks.
- OpenAI Codex CLI: paid, GA hooks.
- GitHub Copilot CLI (the new agentic `copilot`, GA Feb 2026): paid Copilot tier, governed default, preToolUse/postToolUse hooks. Not the old suggest-only `gh copilot`.
- Google Antigravity CLI (GA May 2026): free Individual preview, governed via Terminal Execution Policy Off, Inspect hooks. This is Google's successor; Gemini CLI itself goes dark for free/Pro/Ultra plans June 18, 2026.
- Amazon Kiro CLI 2.0 (GA April 2026): free tier includes the CLI, governed via `--trust-tools`, pre/post hooks. This is AWS's successor; Amazon Q Developer CLI signups are blocked from May 15, 2026.
- opencode (MIT, free): BYO-key, points at the in-cluster vLLM directly, governed and audited via the `tool.execute.before/after` plugin (native interactive ask hangs headless).
- Goose (Apache-2.0, free): BYO-key, points at the in-cluster vLLM, governed and audited via the PreToolUse/PostToolUse hooks engine (not GOOSE_MODE).
- Cursor CLI: works headless with hook-based governance, but locked to Cursor's hosted models (no in-cluster vLLM) and beta safeguards. Weakest fit.

Name the dead products explicitly so students do not bring them: Gemini CLI (use Antigravity), Amazon Q Developer CLI (use Kiro). Free and open-source options for students without a paid plan: opencode and Goose, both vLLM-ready.

Two LLM roles, not to be confused: the agentic CLI is the builder and runs on the student's own model (their plan, their spend, by design, or the in-cluster vLLM if they use opencode/Goose). The model the deployed platform agents call is the small in-cluster vLLM, with no external spend. The no-external-spend rule applies to the deployed demo agent, not to the student's build CLI. (June 19, 2026)

## D14. RESOLVED: per-agent attribution works across the modern agentic CLIs

The earlier claim that per-agent attribution works cleanly only on Claude Code and Codex was wrong, corrected by the per-vendor spikes. Every CLI in the D13 working set now ships lifecycle hooks suitable for a per-action audit trail: Claude Code (PreToolUse/PostToolUse), Codex (GA hooks), GitHub Copilot CLI (preToolUse/postToolUse), Antigravity (Inspect hooks), Kiro (pre/post hooks), opencode (tool.execute.before/after), Goose (PreToolUse/PostToolUse engine), Cursor (six CLI events as of April 2026). The config differs per CLI, but each can ship a structured line per tool invocation to Loki. Per-agent attribution is achievable across the accepted set. The repo wires it for Claude Code and documents the label contract, which the others can meet with their own hook config. No narrowing needed. (June 19, 2026)

## D12. Tempo over Jaeger; KEDA is not Karpenter

Tracing backend is Grafana Tempo, not Jaeger, to keep traces, logs, metrics, and dashboards under one Grafana pane. Jaeger is documented as an alternative path. KEDA (event-driven pod autoscaling) is a platform capability students learn; it is not a Karpenter substitute. Node provisioning is the fixed managed node group, and self-managed Karpenter is not used (see D9). (June 19, 2026)

## D15. RESOLVED: the cluster shape is one t3.2xlarge with prefix delegation

Resolved by end-to-end validation: one t3.2xlarge with VPC CNI prefix delegation and an explicit
maxPods=110. Prefix delegation is required, because the full platform needs roughly 75 pods and the
default t3.2xlarge caps at 58. It consumes about 112 IPs per node, which is what drives the subnet
sizing in `provision/main.tf`.

Two details from the same work are worth keeping. EKS owns the control-plane log group
(`create_cloudwatch_log_group = false`), so a cluster name can be reused without colliding on a log
group that survived the previous destroy. And every resource carries a `Workshop=packt` tag, which
is what makes teardown able to find the load balancers and volumes Terraform does not own.
(June 21, 2026)

## D16. RESOLVED: workload identity is EKS Pod Identity, not IRSA

Every in-cluster workload that needs AWS permissions uses EKS Pod Identity. This covers both the AWS Load Balancer Controller and the EBS CSI driver. The cluster sets `enable_irsa = false`, so no OIDC provider is created.

Why: Pod Identity is the AWS-suggested default over IRSA as of 2026-07 (verified live against the official EKS EBS CSI docs; IRSA is still supported, not deprecated). At fleet scale IRSA would mean one OIDC provider plus a per-cluster trust policy for all 300 clusters; Pod Identity uses a reusable scoped role plus a simple per-cluster association. Being on the legacy path invites an avoidable "why not the modern default" ding on a repo students copy.

Wiring: the LB controller (a Helm chart deployed by ArgoCD) uses a standalone Pod Identity association (`module.aws_lb_controller_pod_identity`, `associations` populated). The EBS CSI driver (an EKS add-on) wires its association through the add-on's `pod_identity_association`, so `module.ebs_csi_pod_identity` creates role and policy only (`associations = {}`) and EKS owns the association ordering: no window where the controller starts without credentials. The `eks-pod-identity-agent` add-on is installed on every cluster. Terraform in `provision/main.tf`; validated (fmt, init, validate) and committed (7a49282).

Supersedes the earlier split ("EBS CSI via IRSA, Pod Identity for the LB controller") recorded in the build spec §6.3 and the cluster module comments before this date. (July 18, 2026)

## D16-validation. D16 proven on a live cluster (Pod Identity delivers working creds)

On 2026-07-18 a throwaway single-node cluster was stood up to prove D16 end to end, not just that the HCL validates. Results:

- No IAM OIDC provider was created in the account (`enable_irsa = false` holds): IRSA is off.
- The `eks-pod-identity-agent` add-on came up ACTIVE, and both associations exist: `kube-system/ebs-csi-controller-sa` and `kube-system/aws-load-balancer-controller`.
- Credential proof, EBS CSI: a pod running as `ebs-csi-controller-sa` called `sts get-caller-identity` and assumed its EBS CSI role. A `gp3` PVC (`ebs.csi.aws.com`) then bound in seconds; the consumer pod mounted the real EBS volume, wrote, and read back. Provisioning an EBS volume requires `ec2:CreateVolume`, so this proves the add-on-native association gives the driver working credentials with EKS owning the ordering.
- Credential proof, LB controller: a pod running as the `aws-load-balancer-controller` SA assumed its load balancer controller role via the standalone association. The controller itself was not installed; the association delivers credentials to that SA regardless.

Teardown was clean: the CSI-provisioned EBS volume was deleted first (via PVC deletion) so it could not leak past `terraform destroy`, confirmed `available` then gone, then the cluster was destroyed (43 resources, destroy-only plan). D16 stands as written. (July 18, 2026)

## D17. RESOLVED: node root disk is 50 GB via block_device_mappings, not disk_size

The dev-cluster node group sized its root volume with `disk_size = 80`, which never took effect. terraform-aws-modules/eks manages a launch template for the node group by default, and `disk_size` is silently ignored whenever a launch template exists, so the node booted at the AL2023 AMI default of 20 GB. The image-heavy platform (the baked vLLM image alone is several GB) overflowed 20 GB, DiskPressure went True, and kubelet evicted the platform on a loop.

Fix: size the root volume through `block_device_mappings` (the launch-template path that actually applies), and set it to a measured value. On a live full-platform build the node rootfs used 34.4 GB, of which container images were 29.8 GB and pod writable layers were a few hundred MB. 50 GB is the resolved size: it holds ~35 GB used at ~69% of imagefs, which stays below kubelet's default 85% image-GC high threshold (so the baked vLLM image is never garbage-collected mid-build) and far above the 10% hard-eviction floor. 40 GB would sit at 86%, above the GC threshold, so sub-50 is unsafe; 80 and 100 were unjustified over-provisioning. `disk_size` is left out with a comment so it is not re-added. (July 19, 2026)

## D18. Manifest fixes found while building the AI plane (v1alpha2 field, non-root UID)

Building the AI plane on a development cluster surfaced three manifest defects, every one of which
would have broken any build the same way:

- demo-agent ModelConfig used `spec.apiKeySecretRef`; the installed `kagent.dev/v1alpha2` ModelConfig CRD names the field `apiKeySecret` (verified against the cluster's CRD schema). Corrected in `solution/platform/2-ai-plane/demo-agent/manifests/demo-agent.yaml`.
- vLLM (KServe `qwen3`) and llm-guard both set `runAsNonRoot: true` on images whose declared USER is non-numeric (vLLM base runs as root; llm-guard declares `user`), which kubelet refuses to start because it cannot verify non-root from a non-numeric user. Fixed by pinning an explicit numeric `runAsUser`: llm-guard to 1000 (matching the image's `user`, which owns the baked scanner-model cache), and vLLM to 1001 plus `HOME=/tmp` (writable cache) and `USER=vllm` (so torch's `getpass.getuser()` does not hit `pwd.getpwuid()` for a uid with no `/etc/passwd` entry).

These are committed manifest changes, not live patches, so a fresh build gets the working versions. (July 19, 2026)

## D19. ArgoCD reads from a Git host it can reach without a credential

Every git-sourced Application resolves its manifests from a repository ArgoCD must be able to read.
With no registered credential, each one fails with `authentication required: Repository not found`
and does so quietly: the Application reports a sync failure while the Helm-sourced components around
it stay green, so the platform looks mostly healthy with its whole AI plane dark.

The resolution is the in-cluster Gitea. Each cluster hosts its own Git remote, the repository is
public within the cluster so ArgoCD needs no credential at all, and you get a remote you can push to,
which a read-only external repository would not give you. Nothing in the reconcile path leaves the
cluster. (July 19, 2026)

## D20. Foundation Kyverno policies ship in Audit, not Enforce (install first, enforce last)

The foundation `policy-baseline` ClusterPolicies (require-resource-limits,
restrict-image-registries, disallow-privileged, require-probes, require-labels) all set
`failureAction: Enforce`, while the AI-plane `ai-policies` set all ship `Audit`. That
split is the defect: an admission guardrail in Enforce mode rejects any pod that violates
it at admission time, including the pods of the very software the platform is still
installing. Kyverno enforcing a resource-limits or probe or registry invariant on the
`demo-apps` tenant namespace before the golden-path workload that satisfies it is deployed
denies that workload and stalls the build. This fails identically on every one of the 300
student clusters, where each student's Claude Code builds the platform live and cannot
proceed past a guardrail that blocks its own installs.

Fix: flip all five foundation rules to `failureAction: Audit`, matching the AI-plane set.
Audit reports violations to `PolicyReport`/`ClusterPolicyReport` without blocking
admission, so the whole platform lands governed but unblocked. Enforcement is turned on
only after the platform is healthy. The single sanctioned flip to Enforce during the
workshop is the B16/P16 governance demo on the AI-plane policies; the foundation baseline
stays Audit through the event (report-only is the correct posture for operational
best-practice rules a live-built platform is still converging toward). The install-first,
enforce-last principle is now a locked GitOps rule in the repo CLAUDE.md so a student's
Claude Code will not re-introduce an enforcing guardrail ahead of its backing workload.
This also closes a live/spec drift: the development cluster already had these
policies patched to Audit live; the manifest now matches. (July 20, 2026)

## D21. The student terminal gets AWS access via EKS Pod Identity, not an IAM user and access key

The VTT previously received AWS credentials from a per-cluster IAM user whose access key
the provisioning script rotated on every run. That rotation was not a preference, it was
forced: AWS returns an access key's secret exactly once, so a script that cannot read an
existing key must delete and re-mint to obtain a usable pair. The consequences were a
non-idempotent provisioning step, a window where the key held by the running pod had just
been invalidated, an IAM propagation delay before a fresh key worked, and 250 users plus
250 keys to create and revoke across the fleet.

Pod Identity removes the credential entirely. The cluster already runs the
eks-pod-identity-agent addon, and terraform already uses this mechanism for the AWS Load
Balancer Controller and the EBS CSI driver, so this is the established pattern on the
cluster rather than a new one. Provisioning now creates a per-cluster role
`packt-student-<cluster>` scoped to `eks:DescribeCluster` on its own cluster ARN plus
`eks:ListClusters`, and a pod identity association on the `workshop/web-terminal`
ServiceAccount. The agent vends short-lived credentials at pod admission. Re-running the
script converges instead of rotating, nothing static exists to leak from the student's
shell, and deleting the cluster deletes the association. The script verifies the identity
by calling `sts:GetCallerIdentity` from inside the pod, because at fleet scale an
unverified provisioning step is 250 unverified steps.

Verified on a live cluster: the terminal assumes its own scoped role, `eks:DescribeCluster`
on its own cluster succeeds, and `ec2:DescribeInstances`, `iam:ListUsers`,
`s3:ListBuckets`, and describe against another cluster in the same account are all denied.

Known and accepted: the student is cluster-admin on their own cluster by design (the
workshop's task is to install a platform, which requires CRDs and ClusterRoles). Pod
Identity resolves credentials by (namespace, ServiceAccount), so a cluster-admin can
schedule a pod using the `aws-load-balancer-controller` ServiceAccount and receive that
role. This was confirmed empirically on a live cluster. The effective AWS reach is
therefore the union of the Pod Identity roles present on their cluster, and tightening the
terminal's own role does not change that. What the union does NOT contain is the ability
to launch compute: no role on a student cluster holds `ec2:RunInstances` or `iam:PassRole`,
Karpenter is deliberately not deployed (see the build spec), and the managed node group is
a fixed shape. What it does contain is the load balancer controller policy's unconditional
`ec2:CreateSecurityGroup`, `ec2:AuthorizeSecurityGroupIngress`,
`ec2:RevokeSecurityGroupIngress`, and `elasticloadbalancing` listener and rule
create/delete/modify on `Resource: "*"`, which with roughly 50 clusters per account is an
account-wide reach. The containment boundary is the AWS account, not intra-cluster RBAC.
Node credentials are a lesser path: IMDS is already set to hop limit 1 with tokens
required, so only a hostNetwork pod reaches them, and the node role carries just the CNI,
ECR read, and worker node policies. (July 21, 2026)
