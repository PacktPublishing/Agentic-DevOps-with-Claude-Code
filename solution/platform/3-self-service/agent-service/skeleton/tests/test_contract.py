# ABOUTME: Contract tests for a generated agent service. Runs offline, before the cluster.
# ABOUTME: Asserts names line up, labels and required controls survived, no placeholder escaped.
"""Local contract tests for this generated agent service.

These run against the files in this repository, with no cluster and no network, so a
developer can prove the golden path produced a governed service before ArgoCD has
reconciled anything.

Run them with:

    uv run --with pytest --with pyyaml python -m pytest -q tests/test_contract.py

Note on the placeholder check: the Backstage scaffolder renders every file in the
skeleton through nunjucks, so this file must never contain a literal opening delimiter.
The pattern below is built from an escaped regex for exactly that reason. Do not
"simplify" it into a plain string, or scaffolding will consume it and the check will
silently pass on every repository.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
MANIFESTS = REPO / "manifests"

# Matches an unrendered scaffolder delimiter or a provisioning token. Written escaped so
# the literal delimiter never appears in this file. See the module docstring.
UNRENDERED = re.compile(r"\$\{\{|REPLACE_WITH_")

# Annotations the AI-plane Kyverno policies require on a generated agent:
# ai-require-llm-guard-reference and ai-require-otel-annotations.
LLM_GUARD_ANNOTATION = "agentic-platform.io/llm-guard-policy"
OTEL_ANNOTATION = "instrumentation.opentelemetry.io/inject-python"

PART_OF_LABEL = "app.kubernetes.io/part-of"
PART_OF_VALUE = "agentic-platform"

# The agent's OWN Service, which kagent's controller creates when it reconciles the Agent CR: a
# Deployment and a Service, both named after the agent, in the agent's namespace, on port 8080.
#
# Verified in kagent v0.9.9 source rather than in the chart, which is the mistake a previous
# revision of this file made. manifest_builder.go buildWorkloadObjects returns both objects with
# objectMeta() taking Name from m.agent.GetName(); deployments.go sets `port := int32(8080)` for the
# container and the Service alike. The Helm chart ships only the controller's own Service, so a
# Service the controller creates at reconcile time is simply not in it. Re-check both when the
# kagent pin moves.
AGENT_SERVICE_PORT = 8080


def _load(name):
    path = MANIFESTS / name
    assert path.is_file(), f"{path.relative_to(REPO)} is missing from the generated repository"
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def agent():
    return _load("agent.yaml")


@pytest.fixture(scope="module")
def route():
    return _load("httproute.yaml")


@pytest.fixture(scope="module")
def component():
    path = REPO / "catalog-info.yaml"
    assert path.is_file(), "catalog-info.yaml is missing; the catalog cannot register this service"
    return yaml.safe_load(path.read_text())


def test_names_agree_across_the_service(agent, route, component):
    """One service, one name, in the Agent, the route, the route path and the catalog."""
    name = agent["metadata"]["name"]
    assert name, "the Agent has no metadata.name"
    assert route["metadata"]["name"] == name, (
        f"route is named {route['metadata']['name']!r} but the Agent is {name!r}; "
        "the ApplicationSet and the catalog key off a single name"
    )
    assert component["metadata"]["name"] == name, (
        f"catalog component is {component['metadata']['name']!r} but the Agent is {name!r}"
    )
    paths = [
        match["path"]["value"]
        for rule in route["spec"]["rules"]
        for match in rule["matches"]
    ]
    assert f"/agents/{name}" in paths, (
        f"no route path for /agents/{name}; found {paths}. Traffic would not reach this agent."
    )


def test_platform_labels_are_present(agent, route):
    """Both objects carry the part-of label the platform selects and reports on."""
    for kind, doc in (("Agent", agent), ("HTTPRoute", route)):
        labels = doc["metadata"].get("labels") or {}
        assert labels.get(PART_OF_LABEL) == PART_OF_VALUE, (
            f"{kind} is missing {PART_OF_LABEL}={PART_OF_VALUE}; "
            "platform dashboards and the ApplicationSet select on it"
        )


def test_no_placeholder_escaped_the_scaffolder():
    """An unrendered token leaves the Application Degraded forever, with no obvious cause."""
    offenders = []
    for path in sorted(REPO.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path == Path(__file__):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if UNRENDERED.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    assert not offenders, "unrendered placeholders survived scaffolding:\n" + "\n".join(offenders)


def test_required_controls_survived_generation(agent, route):
    """The governance the golden path promises: guardrail, tracing, and a mediated path."""
    annotations = agent["metadata"].get("annotations") or {}
    assert annotations.get(LLM_GUARD_ANNOTATION), (
        f"Agent is missing the {LLM_GUARD_ANNOTATION} annotation; "
        "ai-require-llm-guard-reference will flag it and prompts go unscreened"
    )
    assert annotations.get(OTEL_ANNOTATION), (
        f"Agent is missing the {OTEL_ANNOTATION} annotation; "
        "ai-require-otel-annotations will flag it and the agent produces no gen_ai spans"
    )

    parents = [parent["name"] for parent in route["spec"]["parentRefs"]]
    assert "agentgateway" in parents, (
        f"route attaches to {parents}, not agentgateway; traffic would bypass LLM Guard "
        "and the audit access log"
    )

    backends = [
        (backend["name"], backend.get("port"))
        for rule in route["spec"]["rules"]
        for backend in rule.get("backendRefs", [])
    ]
    # In the generated repository the scaffolder has already rendered the agent's name, and the
    # route and its backend both carry it, so they must agree without this test needing to know
    # what the name is.
    agent_name = route["metadata"]["name"]
    assert (agent_name, AGENT_SERVICE_PORT) in backends, (
        f"route backend is {backends}, expected ('{agent_name}', {AGENT_SERVICE_PORT}). "
        "kagent creates a Service named after the agent on 8080; routing anywhere else, including "
        "to the shared controller, does not reach the agent."
    )
