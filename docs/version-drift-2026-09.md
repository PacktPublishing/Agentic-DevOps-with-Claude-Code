<!-- ABOUTME: A dated, verified record of how far each pin has drifted from upstream, and the order -->
<!-- ABOUTME: to move them in. Measured against live sources on 2026-09-05, not read off a report. -->

# Version drift, measured 2026-09-05

Every number here was read from the upstream source on 2026-09-05: Helm repository `index.yaml`
files, the GitHub releases API, and PyPI. Pre-releases are excluded, which matters for Kyverno,
whose newest tag on the day was `3.9.0-rc.4`.

**Nothing has been bumped.** This is the survey, not the change. The repo's own standard is that a
version bump is done when the phase suite passes against it, not when the number changes, and that
suite needs a cluster. Bumping fifteen components untested would replace a known-good platform with
an unverified one, which is the opposite of what pinning is for.

## Foundation

| Component | Pinned chart | Latest stable | App version upstream |
|---|---|---|---|
| argo-cd | 9.5.22 | **10.8.0** | v3.5.2 |
| argo-workflows | 1.0.16 | **2.0.4** | v4.1.2 |
| argo-events | 2.4.22 | 2.4.25 | v1.9.11 |
| argo-rollouts | 2.41.0 | 2.43.0 | v1.10.0 |
| backstage | 2.8.2 | 2.10.0 | |
| kyverno | 3.8.1 | 3.9.0 | v1.19.0 |
| external-secrets | 2.6.0 | **2.10.0** | v2.10.0 |
| openbao | 0.28.4 | 0.29.4 | v2.6.2 |
| keda | 2.20.1 | 2.20.2 | 2.20.2 |
| aws-load-balancer-controller | 3.4.0 | 3.5.0 | v3.5.0 |
| aws-ebs-csi-driver | 2.62.0 | 2.65.1 | 1.65.0 |
| kube-prometheus-stack | 86.3.2 | **89.2.2** | operator v0.93.1 |
| opentelemetry-collector | 0.158.2 | **0.172.0** | 0.159.0 |
| opentelemetry-operator | 0.115.0 | 0.122.0 | 0.158.0 |
| gitea | 12.6.0 | 12.7.0 | 1.27.0 |
| loki | 17.4.7 | **18.12.1** | 3.7.7 |
| tempo | 1.25.0 | 2.3.0 | 2.10.8. **Do not take**, see below |

## AI plane and the rest

| Component | Pinned | Latest | Note |
|---|---|---|---|
| vllm | v0.23.0 | **v0.28.0** | 2026-08-26 |
| kserve | v0.19.0 | v0.20.0 | |
| kgateway | v2.3.4 | v2.4.4 | |
| agentgateway | v1.3.0 | **v1.5.0** | CRD schemas must be re-verified; the manifests are validated against the vendored v1.3.0 CRDs |
| kagent | v0.9.9 | **v0.10.0** | released 2026-09-04, one day before this survey |
| llm-d | v0.7.0 | v0.9.0 | shipped as an architecture reference, not a runtime install |
| gateway-api | v1.5.1 | v1.6.2 | routine. Client-cert mTLS is already available at v1.5.1 via `spec.tls.frontend` |
| openllmetry | 0.61.0 | 0.62.3 | |
| score-k8s | 0.14.0 | 0.17.0 | **orphan**: pinned but used nowhere in the build. Remove the pin or add the content |
| llm-guard | 0.3.16 | 0.3.16 | **archived upstream**, see below |
| mcp spec | 2025-11-25 | **2026-07-28** | breaking; see the MCP section |

## Three findings that are not just numbers

### llm-guard is archived, not dormant

`components.yaml` described it as "dormant since Sept 2025". It is **archived**: GitHub reports
`archived: true`, last push 2026-07-08, PyPI 0.3.16 dating from 2025-05-19, 38 issues left open.

An archived repository is read-only, so **no CVE in this dependency will ever be fixed upstream**.
That matters more here than for an ordinary pin, because this is the prompt-injection scanner, the
component whose entire job is to be attacked. The swap should be chosen now, while it is a decision,
rather than at disclosure, when it is an incident.

### The Tempo pin stays, and the tracking condition is misleading

The note said "do not upgrade back into the 2.10 line until #6436 is closed and the fix version
confirmed". #6436 **is** closed. It was closed by the reporter resolving their own configuration,
adding Kafka and `partition_ring_live_store`, not by a Tempo fix.

So the closure says nothing about whether 2.10 works here, and the second half of the condition,
confirming a fix version, cannot be satisfied because there is no fix. What justifies the pin is the
repo's own empirical result on 2026-07-23: on 2.10 a trace written then queried came back empty and
the test failed. Lifting the pin needs that test rerun, not an issue-tracker check.

Anyone bumping it because the linked issue went green reintroduces a failure the repo already paid
to find. The note in `components.yaml` now says so.

### MCP 2026-07-28 is breaking, and the pin is not the thing to change first

Read from the specification's own changelog: the revision removes protocol-level sessions and the
`Mcp-Session-Id` header, removes the `initialize`/`notifications/initialized` handshake in favour of
per-request `_meta`, removes `ping` and `logging/setLevel`, replaces the GET endpoint and
`resources/subscribe` with `subscriptions/listen`, and drops SSE resumability.

This repo does not implement MCP. It deploys the reference `everything` server and connects kagent
to it, so what must agree is **those two implementations**, not this repo and the newest
specification. Bumping the spec pin while the deployed server and the kagent client still speak
2025-11-25 would document a revision the platform does not run.

Streamable HTTP remains correct either way, and HTTP+SSE remains deprecated, so the transport choice
in the manifests does not change.

The order is: confirm kagent v0.10.0's MCP client revision, confirm an `everything` server image
that speaks 2026-07-28, then move all three together.

## Suggested order when a cluster is available

1. **Patch and minor bumps with no known behaviour change**: argo-events, argo-rollouts, keda,
   openbao, gitea, aws-load-balancer-controller, aws-ebs-csi-driver, opentelemetry-operator. Low
   risk, and clears most of the table.
2. **kube-prometheus-stack, opentelemetry-collector, loki**. Larger jumps, and the observability
   plane has its own phase test to prove them.
3. **argo-cd 9.5.22 to 10.8.0.** Deliberately late. From Argo CD 3.5 the Helm renderer is the v4
   binary, so this is the bump most likely to surface breakage in charts that have nothing to do
   with Argo CD. Re-render everything after it.
4. **argo-workflows 1.0.16 to 2.0.4**, a major chart jump, on its own.
5. **agentgateway and kagent together**, re-vendoring the CRDs first, because
   `tests/test_agentgateway_manifests.py` validates the custom resources against the vendored
   schemas and will fail loudly if a field moved. That test is the reason this bump is safe to
   attempt at all.
6. **vLLM and KServe**, then rerun `inference_probe.py` and `benchmark_inference.py`.
7. **Leave Tempo and llm-guard**, for the reasons above.

## Correction: mTLS is available and always was

An earlier revision of this file reported that client-certificate mTLS could not be configured on
the pinned Gateway API. **That was wrong.** It came from checking
`listeners[].tls.frontendValidation`, which was removed in v1.4.0, and not checking
`spec.tls.frontend`, which is where client validation lives and which is in the standard channel at
v1.5.1:

```
spec.tls.frontend.default.validation.mode enum: ['AllowValidOnly', 'AllowInsecureFallback']
                              .caCertificateRefs: [group, kind, name, namespace]
```

Bumping gateway-api changes nothing here, in either direction. The capability is present at the
pinned version, so the drift table's gateway-api row is a routine bump with no bearing on mTLS.

## Suggested order when a cluster is available

1. **Patch and minor bumps with no known behaviour change**: argo-events, argo-rollouts, keda,
   openbao, gitea, aws-load-balancer-controller, aws-ebs-csi-driver, opentelemetry-operator. Low
   risk, and clears most of the table.
2. **kube-prometheus-stack, opentelemetry-collector, loki**. Larger jumps, and the observability
   plane has its own phase test to prove them.
3. **argo-cd 9.5.22 to 10.8.0.** Deliberately late. From Argo CD 3.5 the Helm renderer is the v4
   binary, so this is the bump most likely to surface breakage in charts that have nothing to do
   with Argo CD. Re-render everything after it.
4. **argo-workflows 1.0.16 to 2.0.4**, a major chart jump, on its own.
5. **agentgateway and kagent together**, re-vendoring the CRDs first, because
   `tests/test_agentgateway_manifests.py` validates the custom resources against the vendored
   schemas and will fail loudly if a field moved. That test is the reason this bump is safe to
   attempt at all.
6. **vLLM and KServe**, then rerun `inference_probe.py` and `benchmark_inference.py`.
7. **Leave Tempo and llm-guard**, for the reasons above.

<!-- mtls-claim-exempt: the section below reports that mTLS remains UNAVAILABLE on the pinned
     Gateway API, so it names the word without asserting the control. -->

## The mTLS blocker survives the Gateway API bump

Checked rather than assumed, since a newer Gateway API was the obvious way the mTLS decision might
have reversed. It has not. In **v1.6.2**, the standard channel still exposes only
`certificateRefs`, `mode` and `options` on a listener, in both `v1` and `v1beta1`:

```
v1.6.2 v1      listener.tls: ['certificateRefs', 'mode', 'options']
v1.6.2 v1beta1 listener.tls: ['certificateRefs', 'mode', 'options']
```

No `frontendValidation`, so no `AllowValidOnly`. Bumping gateway-api from v1.5.1 to v1.6.2 does not
unblock mTLS, and the decision to drop the claim stands. Re-check on the next minor rather than
assuming it will keep being true.
