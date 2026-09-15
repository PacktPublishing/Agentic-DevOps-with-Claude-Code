#!/usr/bin/env python3
# ABOUTME: CI check for components.yaml. Fails if any component lacks a pinned
# ABOUTME: version. No count assertion: the set is the right set, not a number.
"""Validate the component manifest.

Every component must have a non-empty app_version. Components installed via Helm
must also have a non-empty chart_version. The check exits nonzero and prints the
offending entries when a pin is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

HELM_METHODS = {"helm", "helm-oci"}


def validate(data: dict) -> list[str]:
    """Return a list of human-readable errors, empty when the manifest is valid.

    Args:
        data: The parsed components.yaml document.

    Returns:
        A list of error strings, one per problem found.
    """
    errors: list[str] = []
    components = data.get("components")
    if not components:
        return ["components.yaml has no components"]

    for index, component in enumerate(components):
        name = component.get("name") or f"<entry {index}>"

        if not component.get("app_version"):
            errors.append(f"{name}: missing app_version")

        if not component.get("plane"):
            errors.append(f"{name}: missing plane")

        if component.get("install_method") in HELM_METHODS and not component.get("chart_version"):
            errors.append(f"{name}: helm install without a pinned chart_version")

        for item in component.get("bundled") or []:
            item_name = item.get("name") or "<unnamed>"
            if not item.get("version"):
                errors.append(f"{name}: bundled {item_name} missing version")

    return errors


def main(path: str = "components.yaml") -> int:
    """Load the manifest and report validation results.

    Args:
        path: Path to the components.yaml file.

    Returns:
        Process exit code, 0 when valid and 1 when not.
    """
    manifest = Path(path)
    if not manifest.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 1

    data = yaml.safe_load(manifest.read_text())
    errors = validate(data)

    if errors:
        print("components.yaml failed validation:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    count = len(data["components"])
    print(f"components.yaml is valid: {count} components, all pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
