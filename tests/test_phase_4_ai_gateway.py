# ABOUTME: Phase 4 gate. Gateway API CRDs established, the gateways Ready, a Gateway
# ABOUTME: programmed, and the AI-plane policies present in Audit (not Enforce) mode.
import pytest

from conftest import crd_established, get_json

AI_POLICIES = (
    "ai-require-llm-guard-reference",
    "ai-restrict-image-registries",
    "ai-require-otel-annotations",
    "ai-deny-llm-endpoint-bypass",
)


def _pods_ready(namespace):
    obj = get_json("get", "pods", "-n", namespace)
    pods = obj.get("items", [])
    assert pods, f"no pods in {namespace}"
    for pod in pods:
        if pod.get("status", {}).get("phase") in ("Succeeded",):
            continue
        conds = pod.get("status", {}).get("conditions", [])
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
        assert ready, f"pod not Ready in {namespace}: {pod['metadata']['name']}"


def test_gateway_api_crds_established():
    for crd in (
        "gatewayclasses.gateway.networking.k8s.io",
        "gateways.gateway.networking.k8s.io",
        "httproutes.gateway.networking.k8s.io",
    ):
        assert crd_established(crd), f"Gateway API CRD not Established: {crd}"


def test_kgateway_pods_ready():
    _pods_ready("kgateway-system")


def test_agentgateway_pods_ready():
    _pods_ready("agentgateway")


def test_ai_policies_in_audit_mode():
    for name in AI_POLICIES:
        obj = get_json("get", "clusterpolicy", name)
        for rule in obj.get("spec", {}).get("rules", []):
            action = rule.get("validate", {}).get("failureAction")
            if action is not None:
                assert action == "Audit", f"{name} rule is {action}, expected Audit"


@pytest.mark.integration
def test_a_gateway_is_programmed():
    obj = get_json("get", "gateways", "-A")
    programmed = []
    for gw in obj.get("items", []):
        conds = gw.get("status", {}).get("conditions", [])
        if any(c.get("type") == "Programmed" and c.get("status") == "True" for c in conds):
            programmed.append(gw["metadata"]["name"])
    assert programmed, "no Gateway reports Programmed=True"
