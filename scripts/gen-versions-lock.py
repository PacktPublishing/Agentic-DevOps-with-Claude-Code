#!/usr/bin/env python3
# ABOUTME: Regenerates the component table in versions.lock.md from components.yaml.
# ABOUTME: components.yaml is the source of truth; this keeps the human lookup honest.
"""Regenerate the component table in versions.lock.md from components.yaml.

Chapter 2 tells readers that components.yaml is the machine-readable source of truth and
versions.lock.md is the quick lookup. On 2026-09-10 a migration moved 23 pins and the lock file was
not touched, so the two disagreed on 21 of 31 rows and still advertised a component (Score) that had
been removed. That is precisely the drift the chapter tells readers to prevent.

Only the main component table is generated. Everything above and below it is prose that is written
by hand and stays that way.

Usage:
    python3 scripts/gen-versions-lock.py            # rewrite versions.lock.md in place
    python3 scripts/gen-versions-lock.py --check    # exit 1 if the file is stale
"""
import argparse
import os
import sys

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENTS = os.path.join(REPO_ROOT, "components.yaml")
LOCK = os.path.join(REPO_ROOT, "versions.lock.md")

HEADER = "| Component | App version | Chart | Chart version | Chart repo |"
SEPARATOR = "|---|---|---|---|---|"


def _chart_cells(component):
    """Return (chart, chart_version, chart_repo) as the table prints them.

    A component installed by kubectl, kustomize, a library or a CLI has no chart, and saying so
    with its install method is more useful than an empty cell: it tells a reader why there is no
    version to pin in a chart repo.
    """
    if component.get("chart_name"):
        repo = str(component.get("chart_repo") or "n/a")
        for prefix in ("https://", "http://"):
            if repo.startswith(prefix):
                repo = repo[len(prefix):]
        return component["chart_name"], str(component.get("chart_version") or "n/a"), repo
    method = component.get("install_method", "n/a")
    return f"n/a ({method})", "n/a", "n/a"


def render_rows():
    with open(COMPONENTS) as handle:
        data = yaml.safe_load(handle)

    rows = []
    for component in data["components"]:
        name = component.get("display_name") or component["name"]
        chart, chart_version, repo = _chart_cells(component)
        rows.append(f"| {name} | {component['app_version']} | {chart} | {chart_version} | {repo} |")
        # An umbrella chart delivers several things a reader looks up by their own names, so each
        # bundled capability gets its own row rather than being buried in the parent's notes.
        for item in component.get("bundled") or []:
            rows.append(
                f"| {item['name']} | {item['version']} | (bundled in {chart}) | "
                f"{chart_version} | {repo} |"
            )
    return rows


def render_lock():
    """Return the full lock file with only the component table replaced."""
    with open(LOCK) as handle:
        lines = handle.read().splitlines()

    try:
        start = lines.index(HEADER)
    except ValueError:
        raise SystemExit(f"{LOCK}: could not find the component table header:\n  {HEADER}")

    end = start + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1

    return "\n".join(lines[:start] + [HEADER, SEPARATOR] + render_rows() + lines[end:]) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    args = parser.parse_args()

    rendered = render_lock()
    with open(LOCK) as handle:
        current = handle.read()

    if args.check:
        if rendered != current:
            print("versions.lock.md is stale. Run: python3 scripts/gen-versions-lock.py")
            return 1
        print("versions.lock.md matches components.yaml")
        return 0

    if rendered == current:
        print("versions.lock.md already matches components.yaml")
        return 0
    with open(LOCK, "w") as handle:
        handle.write(rendered)
    print("versions.lock.md regenerated from components.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
