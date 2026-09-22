# ABOUTME: Phase 7 gate. The golden-path template registered, the ApplicationSet
# ABOUTME: generating Applications, and generated agents landing governed.
import json

import pytest

from conftest import get_json, incluster_curl, kubectl


def test_applicationset_exists():
    res = kubectl("get", "applicationset", "agent-services", "-n", "argocd", check=False)
    assert res.returncode == 0, "agent-services ApplicationSet not found"


@pytest.mark.integration
def test_template_registered_in_catalog():
    body = incluster_curl(
        "http://backstage.backstage.svc:7007/api/catalog/entities"
        "?filter=kind=template",
        ns="backstage",
    )
    payload = body.rsplit("\n", 1)[0]
    names = [e.get("metadata", {}).get("name") for e in json.loads(payload)]
    assert "agent-service" in names, f"agent-service template not registered: {names}"


@pytest.mark.integration
def test_applicationset_generates_applications():
    obj = get_json("get", "applications", "-n", "argocd")
    generated = [
        a["metadata"]["name"]
        for a in obj.get("items", [])
        if any(
            o.get("kind") == "ApplicationSet" and o.get("name") == "agent-services"
            for o in a["metadata"].get("ownerReferences", [])
        )
    ]
    assert generated, "ApplicationSet produced no Applications (run the golden path first)"


@pytest.mark.integration
def test_generated_agents_are_governed():
    obj = get_json("get", "agents.kagent.dev", "-n", "kagent")
    agents = obj.get("items", [])
    assert agents, "no agents found"
    for agent in agents:
        ann = agent["metadata"].get("annotations", {})
        assert ann.get("agentic-platform.io/llm-guard-policy"), \
            f"{agent['metadata']['name']} missing LLM Guard reference"
        assert any(k.startswith("instrumentation.opentelemetry.io/inject") for k in ann), \
            f"{agent['metadata']['name']} missing OTel annotation"
