# ABOUTME: Fails when versions.lock.md drifts from components.yaml, the source of truth.
# ABOUTME: Chapter 2 tells readers to prevent exactly this drift, so the repo has to model it.
#
# On 2026-09-10 a migration moved 23 pins and left versions.lock.md untouched. The two files then
# disagreed on 21 of 31 rows, and the lock still advertised Score, which had been removed. Nothing
# caught it; it was found by reading the file. This test is what catches it now.
import importlib.util
import os
import subprocess
import sys

import pytest

yaml = pytest.importorskip("yaml")

from conftest import REPO_ROOT

GENERATOR = os.path.join(REPO_ROOT, "scripts", "gen-versions-lock.py")


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_versions_lock", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_exists():
    assert os.path.exists(GENERATOR), "scripts/gen-versions-lock.py is missing"


def test_lock_file_matches_components_yaml():
    """versions.lock.md must be exactly what the generator produces from components.yaml."""
    generator = _load_generator()
    with open(generator.LOCK) as handle:
        current = handle.read()
    assert generator.render_lock() == current, (
        "versions.lock.md has drifted from components.yaml. "
        "Run: python3 scripts/gen-versions-lock.py"
    )


def test_check_mode_exits_nonzero_when_stale(tmp_path):
    """--check must actually fail on a stale file, not just print.

    A check that always exits 0 is worse than no check: it reports a guarantee it is not making.
    """
    result = subprocess.run(
        [sys.executable, GENERATOR, "--check"], capture_output=True, text=True, cwd=REPO_ROOT
    )
    assert result.returncode == 0, f"lock is stale:\n{result.stdout}{result.stderr}"


def test_every_component_has_a_display_name():
    """The lock table prints a human name, so components.yaml has to carry one.

    Without it the generator falls back to the kebab-case identifier and the table silently
    changes from `AWS Load Balancer Controller` to `aws-load-balancer-controller`.
    """
    with open(os.path.join(REPO_ROOT, "components.yaml")) as handle:
        data = yaml.safe_load(handle)
    missing = [c["name"] for c in data["components"] if not c.get("display_name")]
    assert not missing, f"components without display_name: {missing}"


def test_every_component_appears_in_the_lock():
    """Every component, and every bundled capability, is looked up by name in the lock table."""
    with open(os.path.join(REPO_ROOT, "components.yaml")) as handle:
        data = yaml.safe_load(handle)
    with open(os.path.join(REPO_ROOT, "versions.lock.md")) as handle:
        lock = handle.read()

    missing = []
    for component in data["components"]:
        name = component.get("display_name") or component["name"]
        if f"| {name} |" not in lock:
            missing.append(name)
        for item in component.get("bundled") or []:
            if f"| {item['name']} |" not in lock:
                missing.append(f"{name} -> {item['name']}")
    assert not missing, f"components absent from versions.lock.md: {missing}"


def test_lock_names_no_component_that_was_removed():
    """A row for a component components.yaml no longer declares is stale advertising.

    Score was removed from components.yaml and its row sat in the lock for a week.
    """
    generator = _load_generator()
    with open(os.path.join(REPO_ROOT, "components.yaml")) as handle:
        data = yaml.safe_load(handle)

    known = set()
    for component in data["components"]:
        known.add(component.get("display_name") or component["name"])
        known.add(component["name"])
        for item in component.get("bundled") or []:
            known.add(item["name"])

    with open(generator.LOCK) as handle:
        lines = handle.read().splitlines()
    start = lines.index(generator.HEADER) + 2

    strays = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        name = line.strip().strip("|").split("|")[0].strip()
        if name not in known:
            strays.append(name)
    assert not strays, f"versions.lock.md names components that components.yaml does not: {strays}"
