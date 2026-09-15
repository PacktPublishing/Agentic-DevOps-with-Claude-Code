# ABOUTME: Tests for the components.yaml validator. Covers the real manifest plus
# ABOUTME: missing-pin and missing-field cases.
"""Unit tests for scripts/check_components validate()."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from check_components import validate


def _real_manifest() -> dict:
    text = Path(__file__).resolve().parent.parent.joinpath("components.yaml").read_text()
    return yaml.safe_load(text)


def test_real_manifest_is_valid():
    assert validate(_real_manifest()) == []


def test_missing_app_version_is_reported():
    data = {"components": [{"name": "x", "plane": "ai", "install_method": "kubectl"}]}
    errors = validate(data)
    assert any("missing app_version" in e for e in errors)


def test_helm_without_chart_version_is_reported():
    data = {
        "components": [
            {"name": "x", "plane": "ai", "install_method": "helm", "app_version": "1.0"}
        ]
    }
    errors = validate(data)
    assert any("pinned chart_version" in e for e in errors)


def test_empty_manifest_is_reported():
    assert validate({"components": []}) == ["components.yaml has no components"]


def test_bundled_without_version_is_reported():
    data = {
        "components": [
            {
                "name": "umbrella",
                "plane": "foundation",
                "install_method": "helm",
                "chart_version": "1.0",
                "app_version": "1.0",
                "bundled": [{"name": "sub-a", "version": "2.0"}, {"name": "sub-b"}],
            }
        ]
    }
    errors = validate(data)
    assert any("bundled sub-b missing version" in e for e in errors)
    assert not any("sub-a" in e for e in errors)
