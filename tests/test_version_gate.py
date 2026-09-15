# ABOUTME: Cluster-free tests for the Phase 0 Kubernetes version gate, which broke every reader on
# ABOUTME: the day 1.37 shipped because it allow-listed exact minors instead of setting a floor.
#
# The gate itself needs a cluster, so its comparison logic is extracted into parse_server_minor and
# exercised here. Without this the only way to find out the gate is wrong is to run it against a
# cluster of the wrong version, which is exactly the situation a reader is in when it fails them.
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_phase_0_preflight import MIN_MINOR, parse_server_minor


def test_parses_plain_numeric_fields():
    assert parse_server_minor({"major": "1", "minor": "37"}) == (1, 37)


def test_parses_vendor_suffixed_minor():
    # EKS and GKE report "31+" and similar. int("31+") raises; the gate must not.
    assert parse_server_minor({"major": "1", "minor": "37+"}) == (1, 37)


def test_falls_back_to_gitversion_when_numeric_fields_missing():
    assert parse_server_minor({"gitVersion": "v1.36.4-eks-1a2b3c"}) == (1, 36)


def test_returns_none_when_nothing_parseable():
    assert parse_server_minor({}) is None
    assert parse_server_minor({"gitVersion": "unknown"}) is None


def test_floor_accepts_current_and_future_minors():
    # The defect: 1.37 shipped 2026-08-26 and the old allow-list rejected it. Every minor from the
    # floor upward must pass, including ones that do not exist yet.
    for minor in range(MIN_MINOR, MIN_MINOR + 12):
        assert parse_server_minor({"major": "1", "minor": str(minor)}) >= (1, MIN_MINOR), (
            f"1.{minor} must satisfy the floor"
        )


def test_floor_rejects_end_of_life_minors():
    for minor in range(MIN_MINOR - 6, MIN_MINOR):
        assert parse_server_minor({"major": "1", "minor": str(minor)}) < (1, MIN_MINOR), (
            f"1.{minor} is below the floor and must be rejected"
        )


def test_gate_is_a_floor_not_an_allowlist():
    # Guards against someone reintroducing the original defect. A startswith/allow-list check on
    # exact minor strings is the shape that broke; assert the source does not contain one.
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, "test_phase_0_preflight.py")).read()
    assert not re.search(r'startswith\(\s*\(\s*["\']v?1\.\d+', src), (
        "the version gate has been reverted to an allow-list of exact minors; it must be a floor, "
        "or it will fail every reader again on the next Kubernetes release"
    )
