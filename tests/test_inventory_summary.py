# ABOUTME: The phase test for the chapter 2 lab, asserting the contract in spec/phases/example-inventory.md.
# ABOUTME: Run it before the agent works and it fails on a missing output; that failure is the point.
#
# This is the only test here that is meant to fail on a fresh checkout. Chapter 2 has you run it
# first to prove the environment works and the capability does not, then hand the phase to your
# agent, then run it again. Three tests, one per line of the phase's test criteria:
#
#   Every device has a stable identifier and management address
#   Duplicate addresses fail the test
#   The output contains no credentials
#
# It is excluded from the repository's own suite, because a test that is supposed to be red until
# you do the lab would otherwise make every other run look broken. Run it by name, as the chapter
# prints it:
#
#     python -m pytest tests/test_inventory_summary.py -q
import json
import os
import re

import pytest

from conftest import REPO_ROOT

SUMMARY = os.path.join(REPO_ROOT, "out", "inventory-summary.json")
SCHEMA = os.path.join(REPO_ROOT, "schemas", "inventory-summary.json")
FIXTURE = os.path.join(REPO_ROOT, "fixtures", "device-inventory.json")

# Anything that looks like a secret carried through from the source. The fixture deliberately
# contains one, so this assertion has something to catch.
CREDENTIAL_KEY = re.compile(r"secret|password|passwd|community|token|key$", re.I)


def _summary():
    # The two content tests below have nothing to say until the output exists, so they skip rather
    # than pile three failures on top of the one the chapter prints.
    if not os.path.exists(SUMMARY):
        pytest.skip("no out/inventory-summary.json yet; run the phase first")
    with open(SUMMARY) as handle:
        return json.load(handle)


def test_inventory_summary_exists():
    # Step 1 of the lab. Before the phase runs, this is the failure you want: the output is
    # absent, not the test environment broken.
    # A plain open, so the failure a reader sees is the one the chapter prints:
    # FileNotFoundError: out/inventory-summary.json
    with open(SUMMARY) as handle:
        json.load(handle)


def test_every_device_is_identified_and_addressed_exactly_once():
    jsonschema = pytest.importorskip("jsonschema")
    with open(SCHEMA) as handle:
        schema = json.load(handle)
    summary = _summary()

    # The schema carries the shape: a stable id, a management address, no unexpected fields.
    jsonschema.validate(summary, schema)

    assert summary["device_count"] == len(summary["devices"]), (
        "device_count disagrees with the number of devices listed"
    )

    addresses = [d["management_address"] for d in summary["devices"]]
    duplicates = sorted({a for a in addresses if addresses.count(a) > 1})
    assert not duplicates, f"management addresses must be unique; repeated: {duplicates}"

    with open(FIXTURE) as handle:
        source_ids = {d["id"] for d in json.load(handle)["devices"]}
    unknown = sorted({d["id"] for d in summary["devices"]} - source_ids)
    assert not unknown, (
        f"devices not present in the approved source: {unknown}. "
        "The phase forbids enrichment from anywhere else."
    )


def test_the_summary_carries_no_credentials():
    # The source fixture has an snmp_community on every device. None of it may reach the output.
    summary = _summary()

    def walk(node, path="$"):
        if isinstance(node, dict):
            for key, value in node.items():
                assert not CREDENTIAL_KEY.search(key), f"credential-shaped key at {path}.{key}"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(summary)

    with open(FIXTURE) as handle:
        secrets = {d["snmp_community"] for d in json.load(handle)["devices"]}
    rendered = json.dumps(summary)
    leaked = sorted(s for s in secrets if s in rendered)
    assert not leaked, f"a value from the source credential field reached the output: {leaked}"
