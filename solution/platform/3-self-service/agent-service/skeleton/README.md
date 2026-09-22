# ${{ values.name }}

${{ values.description }}

A governed agent service generated from the platform golden path. It ships with:

- a kagent Agent (`manifests/agent.yaml`) routed to the in-cluster vLLM via the
  `${{ values.modelConfig }}` ModelConfig
- an agentgateway route (`manifests/httproute.yaml`) so traffic is screened by LLM Guard
  and carries mTLS, the prompt guardrail, and audit access logging
- OpenTelemetry injection on by default
- contract tests (`tests/test_contract.py`) that prove the above before the cluster sees it

The platform `agent-services` ApplicationSet deploys `manifests/` automatically once this
repository exists. Owner: `${{ values.owner }}`.

## Check it before you wait on the cluster

The contract tests read the files in this repository. They need no cluster and no network,
so they answer "did the golden path generate a governed service" in under a second:

```bash
uv run --with pytest --with pyyaml python -m pytest -q tests/test_contract.py
```

They assert four things: the Agent, the route, the route path and the catalog entry all
agree on one name; the platform `part-of` label is present; no scaffolder placeholder
survived generation; and the controls the platform requires are intact, meaning the LLM
Guard annotation, OpenTelemetry injection, an agentgateway parent, and the shared
backend, which is the Service kagent creates named after this agent, on port 8080.

If they pass and the Application is still unhealthy, the problem is in the cluster rather
than in this repository, which is the point of running them first.
