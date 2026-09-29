# ABOUTME: Asserts every Terraform module in provision/ is pinned to an exact version.
# ABOUTME: A range lets a module float past the provider the lock file pins, and init fails.
#
# The provider lock file pins providers. It does not pin modules. So a module constrained
# with a range such as "~> 21.0" resolves to whatever is newest on the day someone runs
# terraform init, and that newer module can require a newer provider than the lock allows.
#
# That is exactly what happened here. The eks module was constrained "~> 21.0". When the module
# was proven on a live cluster it resolved to 21.24.0, alongside the aws provider 6.55.0 the lock
# records. Later the same constraint resolved to 21.26.0, which requires aws >= 6.59, and every
# fresh terraform init failed on the first command a reader runs. Nothing in the repository had
# changed. The pins are now the exact versions that ran against a live cluster.
import os
import re

from conftest import REPO_ROOT

MAIN_TF = os.path.join(REPO_ROOT, "provision", "main.tf")
LOCK = os.path.join(REPO_ROOT, "provision", ".terraform.lock.hcl")

MODULE = re.compile(r'module\s+"([^"]+)"\s*\{(.*?)\n\}', re.S)
VERSION = re.compile(r'^\s*version\s*=\s*"([^"]+)"', re.M)
EXACT = re.compile(r"^\d+\.\d+\.\d+$")


def test_every_module_is_pinned_exactly():
    with open(MAIN_TF) as handle:
        text = handle.read()

    modules = MODULE.findall(text)
    assert modules, "no module blocks found in provision/main.tf; the parser has gone stale"

    loose = {}
    for name, body in modules:
        m = VERSION.search(body)
        if not m:
            loose[name] = "(no version)"
        elif not EXACT.match(m.group(1)):
            loose[name] = m.group(1)

    assert not loose, (
        "modules not pinned to an exact version: "
        + ", ".join(f"{k} = {v}" for k, v in sorted(loose.items()))
        + ". A range floats past the provider the lock pins and terraform init fails."
    )


def test_the_provider_lock_is_committed():
    # Without the lock the provider floats as well, which is the same failure one layer down.
    assert os.path.exists(LOCK), "provision/.terraform.lock.hcl must be committed"
