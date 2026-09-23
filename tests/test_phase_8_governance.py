# ABOUTME: Phase 8 gate. AI-plane policies flipped to Enforce, admission denies a
# ABOUTME: violating agent and admits a good one, and tool calls are auditable in Loki.
import subprocess

import pytest

from conftest import KUBECONFIG_FILE, get_json, incluster_curl, needs_cluster
from test_phase_4_ai_gateway import AI_POLICIES

# A minimal Agent missing the LLM Guard annotation (should be denied in Enforce).
VIOLATING_AGENT = """
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: phase8-violating
  namespace: kagent
spec:
  type: Declarative
  declarative:
    modelConfig: vllm-qwen3
    systemMessage: "no guard annotation"
"""

# The same Agent, governed (should be admitted).
GOOD_AGENT = """
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: phase8-good
  namespace: kagent
  annotations:
    agentic-platform.io/llm-guard-policy: default-injection-scan
    instrumentation.opentelemetry.io/inject-python: "true"
spec:
  type: Declarative
  declarative:
    modelConfig: vllm-qwen3
    systemMessage: "governed"
"""


def _apply_dry_run(manifest):
    needs_cluster()
    return subprocess.run(
        ["kubectl", "--kubeconfig", KUBECONFIG_FILE, "apply",
         "--dry-run=server", "-f", "-"],
        input=manifest, capture_output=True, text=True, timeout=60,
    )


def test_ai_policies_in_enforce_mode():
    for name in AI_POLICIES:
        obj = get_json("get", "clusterpolicy", name)
        for rule in obj.get("spec", {}).get("rules", []):
            action = rule.get("validate", {}).get("failureAction")
            if action is not None:
                assert action == "Enforce", f"{name} rule is {action}, expected Enforce"


def test_violating_agent_denied():
    res = _apply_dry_run(VIOLATING_AGENT)
    assert res.returncode != 0, "violating agent was admitted (should be denied)"
    assert "denied" in (res.stderr + res.stdout).lower()


def test_good_agent_admitted():
    res = _apply_dry_run(GOOD_AGENT)
    assert res.returncode == 0, f"good agent was denied: {res.stderr.strip()}"


@pytest.mark.integration
def test_loki_has_attributable_agent_tool_invocations():
    body = incluster_curl(
        "http://loki.observability.svc:3100/loki/api/v1/query",
        # The stream scripts/ship-audit-to-loki.sh actually writes. This queried
        # {namespace="kagent"} |~ "tool", which is a third selector that nothing produces: there is
        # no log shipper for pod logs here, and the collector defines a traces pipeline only, with
        # otlp/tempo as its sole exporter. So the assertion could only ever pass by accident.
        "--get", "--data-urlencode", 'query={job="claude-audit"}',
        ns="observability",
    )
    assert '"result"' in body and '"values"' in body, (
        "no audit lines under job=\"claude-audit\". Before concluding the agent was idle, check "
        "the shipper: Loki rejects out-of-order lines within a stream, so a rejected push looks "
        "exactly like silence."
    )
    # A count alone does not support the governance claim. Lines with no agent identity are worse
    # than none, because a dashboard renders them and the trail reads as complete.
    assert "agent_identity" in body, (
        "audit lines are present but carry no agent_identity label, so nothing in them says who "
        "acted; the trail is not attributable"
    )
