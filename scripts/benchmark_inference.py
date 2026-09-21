#!/usr/bin/env python3
# ABOUTME: Measures CPU inference latency and throughput over N sequential requests, reporting
# ABOUTME: percentiles rather than a mean, and separating first-request cost from steady state.
"""Benchmark the CPU inference path.

Two reasons this reports what it reports.

**Percentiles, not a mean.** Latency here is not normally distributed. A mean over a handful of
requests hides the tail completely, and the tail is what a user experiences as "it hung".

**The first request is excluded by default.** On a cold predictor the first completion pays for
model residency and can be an order of magnitude slower than the rest. Averaging it in produces a
number that describes neither the cold path nor the warm one. It is measured and reported
separately, because it is the number that matters for "how long after deploy is this usable".

Sequential by design: this is a single CPU replica. Concurrency would measure queueing, and the
book's claim is about per-request cost on the validated node shape.

Usage:
    export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
    python scripts/benchmark_inference.py --requests 10
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time

import requests

from _cluster import ClusterError, die, port_forward

DEFAULT_SERVICE = "qwen3-predictor"
DEFAULT_NAMESPACE = "kserve"
DEFAULT_PORT = 80
DEFAULT_MODEL = "qwen3-1.7b"


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest measured value at or above the given rank.

    Explicit rather than statistics.quantiles because that interpolates, which reports a number
    nobody observed. On a ten-request benchmark the p90 should be an actual request's latency.
    """
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = math.ceil(pct / 100.0 * len(ordered))
    idx = min(len(ordered) - 1, max(0, rank - 1))
    return ordered[idx]


def run(base_url: str, model: str, prompt: str, max_tokens: int, n: int, timeout: int):
    latencies: list[float] = []
    tokens: list[int] = []
    for i in range(n):
        started = time.monotonic()
        res = requests.post(
            f"{base_url}/v1/chat/completions",
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens},
            timeout=timeout,
        )
        elapsed = time.monotonic() - started
        res.raise_for_status()
        payload = res.json()
        latencies.append(elapsed)
        tokens.append((payload.get("usage") or {}).get("completion_tokens", 0))
        print(f"  request {i + 1}/{n}: {elapsed:.2f}s, {tokens[-1]} tokens", flush=True)
    return latencies, tokens


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prompt", default="List three Kubernetes controllers.")
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--requests", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--include-first", action="store_true",
                    help="include the cold first request in the percentiles (off by default)")
    args = ap.parse_args(argv)

    if args.requests < 2 and not args.include_first:
        return die("--requests must be at least 2, or pass --include-first; "
                   "the first request is excluded from the steady-state numbers")

    try:
        with port_forward(args.service, args.namespace, args.port) as base:
            print(f"benchmarking {args.model} over {args.requests} sequential requests")
            latencies, tokens = run(base, args.model, args.prompt, args.max_tokens,
                                    args.requests, args.timeout)
    except ClusterError as exc:
        return die(str(exc))
    except requests.RequestException as exc:
        return die(f"benchmark aborted: {exc}")

    first = latencies[0]
    steady = latencies if args.include_first else latencies[1:]
    steady_tokens = tokens if args.include_first else tokens[1:]
    total_tokens = sum(steady_tokens)
    total_time = sum(steady)

    print()
    print(f"first request (cold):  {first:.2f}s")
    print(f"steady-state samples:  {len(steady)}")
    print(f"  median (p50):        {statistics.median(steady):.2f}s")
    print(f"  p90:                 {_percentile(steady, 90):.2f}s")
    print(f"  max:                 {max(steady):.2f}s")
    if total_time > 0:
        print(f"  throughput:          {total_tokens / total_time:.1f} completion tokens/s")
    if first > 2 * statistics.median(steady):
        print()
        print(f"note: the first request took {first / statistics.median(steady):.1f}x the median. "
              "That is model residency, not per-request cost. Warm the predictor before timing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
