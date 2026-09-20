#!/usr/bin/env python3
# ABOUTME: Queries Tempo for GenAI spans and reports which gen_ai.* attributes actually arrived,
# ABOUTME: so a missing attribute is distinguishable from a missing trace.
"""Probe the trace pipeline for GenAI spans.

The failure this exists to separate: "no traces" and "traces without the attributes you need" look
identical from a dashboard that renders empty, and they have completely different causes. The first
is a collector or exporter problem. The second is an instrumentation problem, and no amount of
restarting the collector fixes it.

So this reports the trace count and the attribute coverage separately.

A caveat the book states and this script restates on every run: the OpenTelemetry GenAI semantic
conventions are Development grade. `gen_ai.*` attribute names are current but not stable, and a
future collector or SDK may emit different ones. Treat a coverage miss as a prompt to check the
current conventions, not automatically as a broken pipeline.

Usage:
    export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
    python scripts/trace_probe.py
    python scripts/trace_probe.py --query '{ span.gen_ai.request.model != "" }'
"""

from __future__ import annotations

import argparse
import sys

import requests

from _cluster import ClusterError, die, port_forward

DEFAULT_SERVICE = "tempo"
DEFAULT_NAMESPACE = "observability"
DEFAULT_PORT = 3200
DEFAULT_QUERY = '{ span.gen_ai.request.model != "" }'

# The attributes the AI-plane dashboards and the phase gates rely on. Development grade: current,
# not stable.
EXPECTED_ATTRS = [
    "gen_ai.request.model",
    "gen_ai.system",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
]


def search(base_url: str, query: str, limit: int, timeout: int) -> list[dict]:
    res = requests.get(f"{base_url}/api/search",
                       params={"q": query, "limit": limit}, timeout=timeout)
    res.raise_for_status()
    return res.json().get("traces") or []


def fetch_trace(base_url: str, trace_id: str, timeout: int) -> dict:
    res = requests.get(f"{base_url}/api/traces/{trace_id}", timeout=timeout)
    res.raise_for_status()
    return res.json()


def attrs_in_trace(trace: dict) -> set[str]:
    """Collect every attribute key present on any span in the trace."""
    found: set[str] = set()
    for batch in trace.get("batches", []):
        for scope in batch.get("scopeSpans", []):
            for span in scope.get("spans", []):
                for kv in span.get("attributes", []):
                    if kv.get("key"):
                        found.add(kv["key"])
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--query", default=DEFAULT_QUERY, help="TraceQL")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args(argv)

    try:
        with port_forward(args.service, args.namespace, args.port) as base:
            traces = search(base, args.query, args.limit, args.timeout)
            if not traces:
                print(f"query: {args.query}")
                return die(
                    "no traces matched. That is the pipeline, not the instrumentation: check the "
                    "collector is receiving (otel-collector logs) and that Tempo is not rejecting "
                    "on ingestion. Note Tempo is pinned to 2.9.0 because flushed blocks are "
                    "unsearchable in standalone mode on 2.10 (grafana/tempo#6436), so if you have "
                    "bumped it, a silent empty result is the expected symptom."
                )
            sample = fetch_trace(base, traces[0]["traceID"], args.timeout)
            present = attrs_in_trace(sample)
    except ClusterError as exc:
        return die(str(exc))
    except requests.RequestException as exc:
        return die(f"could not reach Tempo: {exc}")

    print(f"query:   {args.query}")
    print(f"traces:  {len(traces)} matched (inspecting {traces[0]['traceID']})")
    print("attribute coverage on the sampled trace:")
    missing = []
    for attr in EXPECTED_ATTRS:
        ok = attr in present
        print(f"  {'present' if ok else 'MISSING'}  {attr}")
        if not ok:
            missing.append(attr)

    gen_ai_present = sorted(a for a in present if a.startswith("gen_ai."))
    if gen_ai_present:
        print(f"all gen_ai.* attributes seen: {', '.join(gen_ai_present)}")

    if missing:
        print()
        print(f"{len(missing)} expected attribute(s) absent. Traces are arriving, so this is "
              "instrumentation rather than transport. The GenAI conventions are Development grade, "
              "so also confirm the current names before treating this as a defect.")
        return 1
    print("OK: traces present and every expected gen_ai attribute is on the span")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
