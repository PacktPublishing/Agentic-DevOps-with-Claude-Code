# ABOUTME: Every custom resource the platform's readiness depends on needs an ArgoCD health check.
# ABOUTME: Without one ArgoCD assumes Healthy, and the dashboard reports green over a dead component.
#
# On 2026-09-17 this platform reported 39 of 39 Applications Synced and Healthy while the MCP
# server's init container had failed 1,584 times over six hours and the demo agent could load no
# tools. ArgoCD had no health check for an MCPServer, so it assumed the best. A dashboard that
# cannot go red is not a dashboard.
import glob
import os

import pytest

yaml = pytest.importorskip("yaml")

from conftest import REPO_ROOT

VALUES = os.path.join(REPO_ROOT, "solution", "platform", "0-bootstrap", "argocd-values.yaml")

# Kinds whose readiness the platform depends on, mapped to the ArgoCD customization key. Built-in
# Kubernetes kinds are excluded: ArgoCD assesses those itself.
REQUIRED = {
    "MCPServer": "resource.customizations.health.kagent.dev_MCPServer",
    "Agent": "resource.customizations.health.kagent.dev_Agent",
    "InferenceService": "resource.customizations.health.serving.kserve.io_InferenceService",
}


def _customizations():
    with open(VALUES) as handle:
        return yaml.safe_load(handle)["configs"]["cm"]


def test_every_required_kind_has_a_health_check():
    missing = [k for k, key in REQUIRED.items() if key not in _customizations()]
    assert not missing, (
        f"custom resources with no ArgoCD health check: {missing}. ArgoCD reports Healthy for a "
        "resource it cannot assess, so the Application goes green whatever the resource is doing."
    )


def test_health_checks_handle_a_resource_with_no_status():
    """A freshly created resource has no status, and the Lua must not error on it.

    An erroring health script leaves the resource Unknown, which is not Healthy but is also not a
    message anyone can act on.
    """
    for kind, key in REQUIRED.items():
        script = _customizations()[key]
        assert "obj.status ~= nil" in script, (
            f"{kind} health check does not guard against a nil status"
        )
        assert script.strip().endswith("return hs"), (
            f"{kind} health check has no terminal return"
        )


def test_health_checks_can_report_not_healthy():
    """A check that only ever returns Healthy is the gap it is supposed to close."""
    for kind, key in REQUIRED.items():
        script = _customizations()[key]
        assert any(
            state in script for state in ('"Progressing"', '"Degraded"')
        ), f"{kind} health check can only ever return Healthy"


def test_the_required_set_covers_the_custom_resources_the_repo_ships():
    """Guard the list itself, so a new custom resource kind cannot slip in unassessed.

    Only kinds whose readiness gates the platform need a check; the ones listed here are
    deliberately exempt because nothing waits on them to become ready.
    """
    exempt = {
        # Configuration and policy objects, not workloads with a readiness to wait on.
        "Application", "ApplicationSet", "AppProject", "ClusterPolicy", "Policy",
        "Namespace", "ConfigMap", "Secret", "ServiceAccount", "Service",
        "Gateway", "HTTPRoute", "GatewayClass", "ReferenceGrant",
        "AgentgatewayBackend", "AgentgatewayPolicy", "RemoteMCPServer",
        "ModelConfig", "Certificate", "Issuer", "ClusterIssuer",
        "ClusterSecretStore", "SecretStore", "ExternalSecret",
        "StorageClass", "Instrumentation", "OpenTelemetryCollector",
        "ServiceMonitor", "PrometheusRule", "GrafanaDashboard",
        "Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding",
        "PersistentVolumeClaim", "Deployment", "Job", "CronJob", "Pod",
        # Definitions and catalog entries. A CRD, a Backstage Component or Template, a
        # Kustomization and a NetworkPolicy are either applied or not; none has a readiness the
        # platform waits on, so ArgoCD's default assessment is the right one.
        "CustomResourceDefinition", "Component", "Template", "Kustomization", "NetworkPolicy",
    }
    found = set()
    pattern = os.path.join(REPO_ROOT, "solution", "platform", "**", "*.yaml")
    for path in glob.glob(pattern, recursive=True):
        with open(path) as handle:
            try:
                docs = list(yaml.safe_load_all(handle))
            except yaml.YAMLError:
                continue
        for doc in docs:
            if isinstance(doc, dict) and doc.get("kind"):
                found.add(doc["kind"])

    unaccounted = sorted(found - exempt - set(REQUIRED))
    assert not unaccounted, (
        f"kinds neither covered by a health check nor listed exempt: {unaccounted}. Decide which "
        "and add it to REQUIRED or to exempt, rather than letting ArgoCD assume Healthy."
    )
