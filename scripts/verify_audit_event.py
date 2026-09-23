#!/usr/bin/env python3
# ABOUTME: Verifies agent tool-invocation audit events reached Loki and are attributable, so
# ABOUTME: "the agent did something" can be answered with evidence rather than recollection.
"""Verify the audit trail in Loki.

The governance claim this backs is narrow and worth stating precisely: every tool invocation an
agent makes is recorded, and each record says which agent made it. A count alone does not support
that. Lines with no agent identity are worse than no lines, because a dashboard renders them and
the trail looks complete while being unattributable.

So this reports three things separately:
  1. whether any audit lines exist in the window
  2. how many carry an agent identity
  3. which tools were invoked

Loki rejects out-of-order lines within a stream, so a gap here can mean the shipper was rejected
rather than the agent being idle. scripts/ship-audit-to-loki.sh stamps strictly increasing
timestamps per stream for that reason; a sudden zero after a working run is worth checking against
the shipper's output before concluding the agent did nothing.

Usage:
    export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
    python scripts/verify_audit_event.py
    python scripts/verify_audit_event.py --since 24h --expect-tool Bash
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import requests

from _cluster import ClusterError, die, port_forward

DEFAULT_SERVICE = "loki"
DEFAULT_NAMESPACE = "observability"
DEFAULT_PORT = 3100
DEFAULT_QUERY = '{job="claude-audit"}'
IDENTITY_LABELS = ("agent_identity", "agent", "session_id")


def _since_seconds(since: str) -> int:
    """Parse a 30m / 24h / 7d window into seconds.

    Guards the empty string explicitly: indexing [-1] on it raises IndexError, which surfaces as a
    stack trace rather than the argument error the user can act on.
    """
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if not since or since[-1] not in units or not since[:-1].isdigit():
        raise ValueError(f"--since must look like 30m, 24h or 7d; got {since!r}")
    return int(since[:-1]) * units[since[-1]]


def query_range(base_url: str, query: str, since: str, limit: int, timeout: int) -> list[dict]:
    end = time.time()
    start = end - _since_seconds(since)
    res = requests.get(
        f"{base_url}/loki/api/v1/query_range",
        params={"query": query, "start": int(start * 1e9), "end": int(end * 1e9), "limit": limit},
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json().get("data", {}).get("result") or []


def summarise(streams: list[dict]) -> tuple[int, int, dict[str, int], set[str]]:
    """Return (total lines, lines with an identity, tool counts, identities seen)."""
    total = attributed = 0
    tools: dict[str, int] = {}
    identities: set[str] = set()
    for stream in streams:
        labels = stream.get("stream", {})
        label_identity = next((labels[k] for k in IDENTITY_LABELS if labels.get(k)), None)
        for _ts, line in stream.get("values", []):
            total += 1
            identity = label_identity
            tool = None
            try:
                parsed = json.loads(line)
                identity = identity or next(
                    (parsed[k] for k in IDENTITY_LABELS if parsed.get(k)), None
                )
                tool = parsed.get("tool_name") or parsed.get("tool")
            except (ValueError, TypeError):
                pass  # a non-JSON line still counts as an audit line, just an unparseable one
            if identity:
                attributed += 1
                identities.add(str(identity))
            if tool:
                tools[str(tool)] = tools.get(str(tool), 0) + 1
    return total, attributed, tools, identities


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--query", default=DEFAULT_QUERY, help="LogQL stream selector")
    ap.add_argument("--since", default="1h")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--expect-tool", action="append", default=[],
                    help="fail unless this tool appears; repeatable")
    args = ap.parse_args(argv)

    try:
        with port_forward(args.service, args.namespace, args.port) as base:
            streams = query_range(base, args.query, args.since, args.limit, args.timeout)
    except ValueError as exc:
        return die(str(exc))
    except ClusterError as exc:
        return die(str(exc))
    except requests.RequestException as exc:
        return die(f"could not reach Loki: {exc}")

    total, attributed, tools, identities = summarise(streams)
    print(f"query:  {args.query}  (last {args.since})")
    print(f"lines:  {total}")

    if total == 0:
        return die(
            "no audit lines in the window. Before concluding the agent was idle, check the shipper: "
            "scripts/ship-audit-to-loki.sh reads a local JSONL and pushes it, and Loki rejects "
            "out-of-order lines within a stream, so a rejected push looks exactly like silence."
        )

    print(f"attributed: {attributed}/{total} carry an agent identity"
          f"{' (' + ', '.join(sorted(identities)) + ')' if identities else ''}")
    if tools:
        print("tools invoked:")
        for tool, count in sorted(tools.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>5}  {tool}")

    failed = False
    if attributed < total:
        print()
        print(f"{total - attributed} line(s) have no agent identity. Those are not attributable, so "
              "they do not support the governance claim even though a dashboard will render them.")
        failed = True
    for tool in args.expect_tool:
        if tool not in tools:
            print(f"expected tool '{tool}' not found in the window")
            failed = True

    if failed:
        return 1
    print("OK: audit lines present and every line is attributable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
