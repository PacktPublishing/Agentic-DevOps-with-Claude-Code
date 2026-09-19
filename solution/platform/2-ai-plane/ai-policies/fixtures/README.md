<!-- ABOUTME: Maps each Kyverno AI-policy fixture to the policy it trips, for the B16 demo. -->
<!-- ABOUTME: These files live in fixtures/ so ArgoCD never syncs them; apply by hand. -->

# AI-policy denial fixtures

Each fixture is scoped to trip exactly one of the four AI policies in
`../manifests/ai-policies.yaml`. Every other policy is satisfied, so when the
policy set runs in enforce mode the rejection message names one rule and one
rule only. That keeps the on-screen denial unambiguous.

The policies run in **Audit** mode until Phase 8 flips them to **Enforce**. In
Audit mode `kubectl apply` succeeds and Kyverno records a `PolicyReport` entry
instead of blocking. The B16 demo runs after the enforce flip, so the apply is
rejected outright.

ArgoCD syncs only the `manifests/` subdirectory of each component. These
fixtures sit in `fixtures/`, so they are never reconciled onto the cluster. They
exist to be applied by hand and rejected.

| Fixture | Policy tripped | What makes it violate |
|---|---|---|
| `violating-agent.yaml` | `ai-require-llm-guard-reference` | kagent Agent with no `agentic-platform.io/llm-guard-policy` annotation |
| `violating-image.yaml` | `ai-restrict-image-registries` | image is `docker.io/library/nginx`, not `ghcr.io` |
| `violating-otel.yaml` | `ai-require-otel-annotations` | no `instrumentation.opentelemetry.io/inject-*` annotation |
| `violating-endpoint.yaml` | `ai-deny-llm-endpoint-bypass` | `OPENAI_BASE_URL` points at `api.openai.com`, not the in-cluster endpoint |

## B16 primary fixture

The scripted denial demo uses `violating-agent.yaml`. It is a copy of the
demo-agent's Agent with the guardrail annotation removed, so the reason it is
denied is the missing LLM Guard reference and nothing else. That is the point
the demo makes: the platform refuses to admit an agent that has no guardrail.

Run it against the cluster you provisioned this session, with an explicit
kubeconfig:

```bash
KUBECONFIG=/tmp/<cluster>.kubeconfig AWS_PROFILE=<profile> \
  kubectl apply -f violating-agent.yaml
# expected: admission webhook denies, naming ai-require-llm-guard-reference
```

The other three fixtures are there so you can show any single policy in
isolation without the demo turning into a guessing game about which rule fired.
