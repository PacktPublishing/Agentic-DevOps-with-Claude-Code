# ABOUTME: Phase 0 gate. Confirms a bare, correctly-versioned cluster and a valid,
# ABOUTME: fully-pinned components.yaml before any platform install.
import os
import re
import subprocess

import pytest

from conftest import REPO_ROOT, get_json, kubectl


def test_at_least_one_node_ready():
    obj = get_json("get", "nodes")
    ready = []
    for node in obj.get("items", []):
        conds = node.get("status", {}).get("conditions", [])
        if any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds):
            ready.append(node["metadata"]["name"])
    assert ready, "no Ready nodes"


# Oldest Kubernetes minor this platform is tested against. Raise it as minors go end of life;
# do NOT convert this back into an allow-list of exact minors.
#
# An allow-list breaks every reader on the day a new minor ships, which is roughly every 15 weeks
# on the Kubernetes release train, and it fails them at the very first gate with a message implying
# their cluster is wrong when it is simply newer than this file. A floor expresses the real
# requirement: the platform needs at least these APIs, and a later minor is fine.
#
# 1.34 is the floor because it is the oldest minor still supported upstream; it reaches end of life
# on 2026-10-27, at which point raise this to 35. Supported at the time of writing: 1.34 through 1.37.
MIN_MINOR = 34


def parse_server_minor(server_version):
    """Return (major, minor) from a kubectl `version` serverVersion mapping.

    Managed distributions report major/minor with a non-numeric suffix ("1", "31+"), so digits are
    stripped rather than passed to int(), which would raise and present as a broken test instead of
    a cluster that merely reports a vendor suffix. gitVersion is the fallback when the numeric
    fields are absent entirely.
    """
    major = re.sub(r"\D", "", str(server_version.get("major", "")))
    minor = re.sub(r"\D", "", str(server_version.get("minor", "")))
    if not major or not minor:
        m = re.search(r"v?(\d+)\.(\d+)", str(server_version.get("gitVersion", "")))
        if not m:
            return None
        major, minor = m.group(1), m.group(2)
    return int(major), int(minor)


def test_server_version_is_supported():
    server = get_json("version").get("serverVersion", {})
    parsed = parse_server_minor(server)
    assert parsed is not None, f"could not read a version from serverVersion: {server!r}"
    assert parsed >= (1, MIN_MINOR), (
        f"server version {server.get('gitVersion') or parsed} is below the supported floor "
        f"1.{MIN_MINOR}. Upgrade the cluster; older minors are end of life upstream."
    )


def test_argocd_namespace_absent():
    res = kubectl("get", "namespace", "argocd", check=False)
    assert res.returncode != 0, "argocd namespace already exists; cluster is not bare"


def test_no_argocd_applications_yet():
    # The CRD may not exist on a bare cluster; either way there must be no Applications.
    res = kubectl("get", "applications", "-A", check=False)
    if res.returncode == 0:
        assert res.stdout.strip() in ("", "No resources found"), "Applications already exist"


def test_components_yaml_valid_and_pinned():
    # check_components.py parses components.yaml, so it needs pyyaml in the interpreter this
    # shells out to. Skip rather than fail when it is absent, so a bare `pytest` on a fresh
    # checkout reports what it could check instead of one confusing failure.
    pytest.importorskip("yaml")
    res = subprocess.run(
        ["python3", os.path.join(REPO_ROOT, "scripts", "check_components.py")],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"check_components failed: {res.stdout}{res.stderr}"
