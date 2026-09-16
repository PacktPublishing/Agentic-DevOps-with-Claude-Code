# ABOUTME: Phase 1 gate. ArgoCD up, the core foundation Synced/Healthy, a single default
# ABOUTME: gp3 StorageClass, and the OpenBao-backed ESO pull materializing a Secret.
from conftest import assert_apps_healthy, get_json, kubectl


def test_argocd_pods_ready():
    obj = get_json("get", "pods", "-n", "argocd", "-l", "app.kubernetes.io/part-of=argocd")
    pods = obj.get("items", [])
    assert pods, "no ArgoCD pods found"
    for pod in pods:
        conds = pod.get("status", {}).get("conditions", [])
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
        assert ready, f"ArgoCD pod not Ready: {pod['metadata']['name']}"


def test_app_of_apps_synced():
    obj = get_json("get", "application", "platform-foundation", "-n", "argocd")
    assert obj["status"]["sync"]["status"] == "Synced"


def test_core_foundation_healthy():
    assert_apps_healthy("cert-manager", "external-secrets", "openbao", "kyverno")


def test_single_default_storageclass_is_gp3():
    obj = get_json("get", "storageclasses")
    defaults = [
        sc["metadata"]["name"]
        for sc in obj.get("items", [])
        if sc.get("metadata", {})
        .get("annotations", {})
        .get("storageclass.kubernetes.io/is-default-class")
        == "true"
    ]
    assert defaults == ["gp3"], f"expected only gp3 default, got {defaults}"


def test_openbao_clustersecretstore_ready():
    obj = get_json("get", "clustersecretstore", "openbao")
    conds = obj.get("status", {}).get("conditions", [])
    assert any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in conds
    ), "OpenBao ClusterSecretStore not Ready"


def test_demo_externalsecret_materializes_secret():
    # The demo ExternalSecret should produce the target Secret in the openbao namespace.
    res = kubectl("get", "secret", "demo-app-credentials", "-n", "openbao", check=False)
    assert res.returncode == 0, "demo-app-credentials Secret was not materialized by ESO"


def test_no_application_out_of_sync():
    obj = get_json("get", "applications", "-n", "argocd")
    out_of_sync = [
        a["metadata"]["name"]
        for a in obj.get("items", [])
        if a.get("status", {}).get("sync", {}).get("status") == "OutOfSync"
    ]
    assert not out_of_sync, f"OutOfSync Applications: {out_of_sync}"
