# ABOUTME: Contract tests for the platform manifests, covering the defect classes that recur here.
# ABOUTME: Each one is a mistake this repo actually shipped, not a hypothetical.
#
# The recurring classes, every one of which has cost real debugging time:
#
#   1. An unsubstituted REPLACE_WITH_* placeholder, which leaves an Application Degraded forever.
#   2. runAsNonRoot with no numeric runAsUser on an image whose USER is not numeric, which the
#      kubelet refuses with CreateContainerConfigError before the container starts.
#   3. An image repository that repeats the registry host, producing a doubled path.
#   4. A helper image override that no longer resolves.
#   5. A dynamically provisioned volume with no ownership tag, which survives a teardown.
#
# These need no cluster and no cloud account. Each assertion is a failure someone already paid for
# on a live one.
#
# These run without AWS on purpose. Every assertion here is a failure someone already paid for on a
# live cluster, and at fleet scale each one would repeat across 250 clusters in five accounts.
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

from conftest import REPO_ROOT

# The reference build moved from platform/ to solution/platform/ (the restructure that split the
# answer out of the student's empty platform/). These tests validate the reference build, so every
# manifest path is rooted here. Keep this the single source of truth for that location.
PLATFORM = os.path.join(REPO_ROOT, "solution", "platform")

def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()

def _find_repositories(obj):
    # Yield every image.repository value anywhere in a nested Helm valuesObject.
    if isinstance(obj, dict):
        img = obj.get("image")
        if isinstance(img, dict) and isinstance(img.get("repository"), str) and img.get("registry"):
            yield img["repository"]
        for v in obj.values():
            yield from _find_repositories(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_repositories(v)


def test_dynamically_provisioned_volumes_are_tagged_as_ours():
    # The EBS CSI driver applies only its own kubernetes.io/* tags, so PVC volumes carried no
    # Workshop tag. Measured on the live fleet: 100 of 150 volumes were invisible to the orphan
    # sweep, which selects on Workshop=packt. That is two volumes per cluster, 500 at full size,
    # each one billing after its cluster is gone.
    sc_path = os.path.join(PLATFORM, "0-bootstrap", "gp3-storageclass.yaml")
    sc = yaml.safe_load(_read(sc_path))
    params = sc.get("parameters", {})
    tags = {v for k, v in params.items() if k.startswith("tagSpecification_")}
    assert any(t == "Workshop=packt" for t in tags), (
        "the default StorageClass must tag provisioned volumes Workshop=packt, "
        "or the orphan sweep cannot see them"
    )

def test_grafana_ships_no_broken_image_override():
    # There is no seeded fault. The workshop must not manufacture a failure; students hit enough
    # real ones. Grafana uses the chart default image, with no tag override that could break the pull.
    app = os.path.join(PLATFORM, "1-foundation", "kube-prometheus-stack",
                       "application.yaml")
    doc = yaml.safe_load(_read(app))
    grafana = doc["spec"]["source"]["helm"]["valuesObject"]["grafana"]
    assert "image" not in grafana, "grafana must not override its image; no seeded fault"


# --- Per-cluster substitution: the LB controller placeholders ---------------------------------

def test_lb_controller_ships_substitutable_placeholders():
    # The reference build under solution/ is a template and must stay one. Baking one cluster's
    # name, VPC or region in here hands the next reader a manifest that is wrong for them and
    # fails in a way that does not look like a substitution problem.
    #
    # vpcId is templated rather than left to IMDS on purpose: the metadata fetch times out under
    # prefix delegation and the controller crash-loops, leaving the Application Degraded forever.
    app = os.path.join(PLATFORM, "1-foundation",
                       "aws-load-balancer-controller", "application.yaml")
    body = _read(app)
    for token in ("REPLACE_WITH_CLUSTER_NAME", "REPLACE_WITH_VPC_ID", "REPLACE_WITH_REGION"):
        assert token in body, (
            f"{token} must stay a substitutable placeholder in the reference build; "
            "provision/cluster-facts.sh fills it into your working copy under platform/"
        )


def test_working_platform_copy_has_no_unsubstituted_placeholders():
    # The inverse of the test above, for the copy that actually runs. platform/ is the reader's
    # working tree, and a placeholder surviving there leaves the Application Degraded forever while
    # ArgoCD reports the sync succeeded. Skipped on a fresh checkout and in CI, where platform/
    # does not exist yet.
    working = os.path.join(REPO_ROOT, "platform")
    if not os.path.isdir(working):
        pytest.skip("no platform/ working copy yet; create one and run provision/cluster-facts.sh")
    offenders = []
    for root, _, files in os.walk(working):
        for name in files:
            if not name.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(root, name)
            with open(path) as handle:
                for lineno, line in enumerate(handle, 1):
                    if "REPLACE_WITH_" in line:
                        offenders.append(f"{os.path.relpath(path, REPO_ROOT)}:{lineno}")
    assert not offenders, (
        "unsubstituted placeholders under platform/: " + ", ".join(offenders) +
        ". Run provision/cluster-facts.sh."
    )

def test_openbao_seed_job_runs_as_the_image_uid():
    # runAsNonRoot without a numeric runAsUser fails with CreateContainerConfigError because kubelet
    # cannot verify non-root from the image's non-numeric user (uid 100 openbao). D18 pattern.
    job = os.path.join(PLATFORM, "1-foundation", "openbao-config",
                       "manifests", "seed-job.yaml")
    doc = yaml.safe_load(_read(job))
    sc = doc["spec"]["template"]["spec"]["securityContext"]
    assert sc.get("runAsUser") == 100, "the OpenBao seed job needs an explicit numeric runAsUser"

def test_no_image_repository_doubles_the_registry_host():
    # The Backstage chart builds the image ref as registry/repository. A repository that repeats the
    # host (repository: ghcr.io/... with registry: ghcr.io) yields ghcr.io/ghcr.io/..., a different
    # path that pulled a broken image and crash-looped. No component may repeat a registry host in
    # its repository field.
    import glob
    bad = []
    for f in glob.glob(os.path.join(PLATFORM, "**", "application.yaml"), recursive=True):
        for docd in yaml.safe_load_all(_read(f)):
            if not isinstance(docd, dict):
                continue
            for repo in _find_repositories(docd):
                if re.search(r"\b(ghcr\.io|docker\.io|quay\.io|public\.ecr\.aws)/", repo):
                    bad.append(f"{os.path.relpath(f, REPO_ROOT)}: repository={repo}")
    assert not bad, "image repository must not include the registry host:\n" + "\n".join(bad)
