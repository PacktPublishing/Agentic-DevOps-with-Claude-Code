#!/usr/bin/env python3
# ABOUTME: Compares every pinned component against its upstream and reports the drift, so the
# ABOUTME: maintenance cadence runs on a schedule instead of on someone remembering.
"""Report how far each pin in components.yaml has drifted from upstream.

Reads Helm repository index files and the GitHub releases API. Pre-releases are excluded, which
matters: the newest Kyverno tag on the day this was written was 3.9.0-rc.4, and a sweep that
reported it as "latest" would invite a pin onto a release candidate.

Exits 0 always by default. Drift is information, not a failure: this platform pins deliberately and
several pins are downgrades held for measured reasons. Use --fail-on-drift in a job that should go
red. The point is that nobody has to remember to look.

Usage:
    python scripts/version_sweep.py
    python scripts/version_sweep.py --format markdown
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Components whose pin is deliberate and must not be reported as neglect. Each needs a reason,
# because "don't upgrade this" with no cause becomes folklore the moment its author leaves.
# Components whose project_url is a docs site or an OCI registry rather than a GitHub repo, so the
# releases API cannot be inferred from it. Without these the sweep silently reports "unknown" for
# most of the AI plane, which is the half most likely to move: a sweep blind to 40% of the stack
# reads as reassurance while telling you nothing.
GITHUB_SOURCE = {
    "gateway-api": "kubernetes-sigs/gateway-api",
    "kgateway": "kgateway-dev/kgateway",
    "agentgateway": "agentgateway/agentgateway",
    "kagent": "kagent-dev/kagent",
    "kserve": "kserve/kserve",
    "vllm": "vllm-project/vllm",
    "llm-d": "llm-d/llm-d",
    "llm-guard": "protectai/llm-guard",
    "cert-manager": "cert-manager/cert-manager",
    "score": "score-spec/score-k8s",
}

HELD = {
    "tempo": "held at 2.9.0: on 2.10 a trace written then queried came back empty in standalone "
             "mode and the phase test failed, measured 2026-07-23. Lift only when that test passes "
             "on a current build, NOT because grafana/tempo#6436 is closed (it was closed by the "
             "reporter fixing their own config, not by a fix).",
    "llm-guard": "archived upstream; there is no newer version and there never will be. The pin is "
                 "not the problem, the dependency is.",
}


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "packt-agentic-devops-version-sweep"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def is_stable(version: str) -> bool:
    return not re.search(r"-(rc|alpha|beta|dev|pre|snapshot)", version, re.I)


def version_key(version: str):
    return [int(n) for n in re.findall(r"\d+", version)[:4]]


def latest_chart(repo_url: str, chart: str, cache: dict) -> str | None:
    if repo_url not in cache:
        try:
            import yaml
            cache[repo_url] = yaml.safe_load(io.BytesIO(fetch(f"{repo_url.rstrip('/')}/index.yaml")))
        except Exception:
            cache[repo_url] = None
    index = cache[repo_url]
    if not index:
        return None
    entries = [e for e in (index.get("entries", {}).get(chart) or []) if is_stable(e["version"])]
    if not entries:
        return None
    return sorted(entries, key=lambda e: version_key(e["version"]))[-1]["version"]


def latest_github(project_url: str, name: str = "") -> str | None:
    slug = GITHUB_SOURCE.get(name)
    if not slug:
        m = re.search(r"github\.com/([^/]+)/([^/#?]+)", project_url or "")
        if not m:
            return None
        slug = f"{m.group(1)}/{m.group(2)}"
    try:
        data = json.loads(fetch(f"https://api.github.com/repos/{slug}/releases/latest"))
    except Exception:
        return None
    return data.get("tag_name")


def normalise(v: str) -> str:
    return (v or "").lstrip("v").strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--format", choices=("text", "markdown"), default="text")
    ap.add_argument("--fail-on-drift", action="store_true",
                    help="exit non-zero when anything has drifted (off by default; drift is news, "
                         "not breakage)")
    args = ap.parse_args(argv)

    import yaml
    manifest = yaml.safe_load((REPO_ROOT / "components.yaml").read_text())
    cache: dict = {}
    drifted, held, unknown = [], [], []

    for comp in manifest["components"]:
        name = comp["name"]
        pinned = comp.get("chart_version") or comp.get("app_version") or ""
        latest = None
        # .get with a default still returns None when the key exists with a null value, which
        # components.yaml uses for non-Helm entries. Coerce rather than assume a string.
        chart_repo = comp.get("chart_repo") or ""
        if chart_repo.startswith("http") and comp.get("chart_name"):
            latest = latest_chart(chart_repo, comp["chart_name"], cache)
        if not latest:
            latest = latest_github(comp.get("project_url") or "", name)
        if name in HELD:
            # Report a held component even when no upstream resolves. llm-guard is archived, so the
            # releases API returns nothing, and letting it fall into "unknown" buries the one note
            # that matters most: there will never be a fix for anything found in it.
            held.append((name, pinned, latest or "no upstream releases"))
        elif not latest:
            unknown.append((name, pinned))
        elif normalise(latest) != normalise(pinned):
            drifted.append((name, pinned, latest))

    if args.format == "markdown":
        print("| Component | Pinned | Latest |")
        print("|---|---|---|")
        for name, pinned, latest in drifted:
            print(f"| {name} | `{pinned}` | **`{latest}`** |")
    else:
        print(f"drifted: {len(drifted)}  held: {len(held)}  unknown: {len(unknown)}")
        for name, pinned, latest in drifted:
            print(f"  {name:<30} {pinned:<14} -> {latest}")
    for name, pinned, latest in held:
        print(f"  HELD {name}: pinned {pinned}, upstream {latest}\n       {HELD[name]}")
    for name, pinned in unknown:
        print(f"  ? {name:<30} {pinned:<14} (no upstream source resolved)")

    return 1 if (args.fail_on_drift and drifted) else 0


if __name__ == "__main__":
    raise SystemExit(main())
