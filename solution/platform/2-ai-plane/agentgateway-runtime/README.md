<!-- ABOUTME: Why the agentgateway data path is a separate component from the controller install, -->
<!-- ABOUTME: and what each manifest here is responsible for. -->

# agentgateway-runtime

The `agentgateway` Application installs the **controller**. This one creates the **data path**.

Keeping them apart matters because the failure they produce together is misleading. A controller
with no Gateway reconciles nothing, every Application still reports Synced and Healthy, and routes
sit `Accepted=False` with "no parent found", which reads as a route defect rather than a missing
Gateway.

| File | What it does |
|---|---|
| `gateway.yaml` | The Gateway, and the namespace label that lets `kagent` routes attach to it |
| `vllm-backend.yaml` | `AgentgatewayBackend` for the in-cluster vLLM, plus the route that reaches it |
| `injection-policy.yaml` | Prompt-guard policy sending requests and responses through LLM Guard |

## Two things that are easy to get wrong

**Listener namespace policy is `Selector`, not `Same`.** The generated agent routes live in
`kagent`, so `Same` silently refuses every route the golden path produces: route exists, Gateway
exists, nothing joins them. `Selector` opts a namespace in by label, which is narrower than `All`
and auditable.

**The guardrail fails closed.** If the scanner is unreachable, prompts are refused rather than
passed unscanned. A guardrail that fails open is one an attacker only has to knock over.

## Schemas are verified, not assumed

Every CR here was validated against the CRDs vendored in `charts-vendor/`, and the first draft was
wrong in ways that would have been rejected at apply time: the API group is `agentgateway.dev`, not
`gateway.agentgateway.dev`; `host`/`port` sit under `spec.ai.provider`, not `spec.ai`; `promptGuard`
lives under `spec.backend.ai` and its `request`/`response` are arrays; and `failureMode` takes
`FailClosed`/`FailOpen`, not `Deny`/`Allow`. `tests/test_agentgateway_manifests.py` runs that
validation without a cluster, so the next schema change fails a test rather than a sync.

## mTLS

`mtls-gateway.yaml` validates client certificates at the edge: a workload without a certificate
signed by `agentgateway-client-ca` cannot complete the handshake, so it is refused before any
application policy runs.

**Client validation is Gateway-wide, through `spec.tls.frontend`, not per-listener.** That matters
because there is an older spelling that looks like the answer and is not.
`listeners[].tls.frontendValidation` existed in Gateway API v1.3.0's experimental channel and was
removed in v1.4.0, when the capability moved to `spec.tls.frontend` in the **standard** channel.

Searching a current release for `frontendValidation` therefore finds nothing, which invites the
conclusion that Gateway API cannot do client-cert mTLS. It can, and this repo previously recorded
the opposite as settled fact and removed the mTLS claim from nine files on the strength of it. The
error was checking one plausible field, finding it absent, and reporting a capability gap without
checking whether the capability had moved.

`mode: AllowValidOnly` is load-bearing. `AllowInsecureFallback` accepts clients with no valid
certificate and defeats the control.

Two tests hold this: one asserts the validation block exists with the right mode and a CA, the other
fails if anyone reintroduces `frontendValidation`, which the API server prunes silently rather than
rejecting, so mTLS would disappear with every Application still green.

## Audit: the claim was made true

The same sentence claimed audit logging, and that was not configured either. Unlike mTLS it is
expressible on the pinned CRD, and it is the half the governance story rests on: a guardrail tells
you a bad prompt was refused, the audit record tells you who asked and when. So `audit-policy.yaml`
configures `frontend.accessLog` to the OTel collector the observability plane already runs, and
`test_audit_logging_is_actually_configured` keeps the claim and the configuration from drifting
apart again.

## Why the Gateway is called `agentgateway-proxy`

The controller creates one Deployment per Gateway, named after the Gateway, in the Gateway's
namespace. The chart that installs the controller is also released as `agentgateway` into namespace
`agentgateway`, and its Deployment carries that name. A Gateway called `agentgateway` therefore
aims the controller's proxy Deployment at the controller's own Deployment, and `spec.selector` is
immutable, so the apply fails permanently.

The failure is quiet. Argo CD reports the sync succeeded, because every manifest applied; the
Gateway carries `Programmed=False` with `field is immutable` buried in a status condition, and the
Application shows Degraded with no bad manifest to find. It was only caught by provisioning a
cluster and reading the Gateway's conditions.

The mTLS Gateway is `agentgateway-mtls` and never had the problem, which is what made the plain
one's failure look like a version regression rather than a name clash.

`tests/test_agentgateway_manifests.py::test_no_gateway_collides_with_a_helm_release_in_its_namespace`
pairs every Gateway against the Helm releases this repo installs into its namespace, so a
recurrence fails the build rather than the cluster.
