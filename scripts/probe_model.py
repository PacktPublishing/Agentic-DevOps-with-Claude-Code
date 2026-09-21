#!/usr/bin/env python3
# ABOUTME: Asks the serving stack which model it is actually serving, via the OpenAI-compatible
# ABOUTME: /v1/models endpoint, and checks the served id matches what the manifests claim.
"""Probe the model endpoint.

The smallest useful question about a serving stack: what does it think it is serving? The
InferenceService can be Ready while the container serves a different model id than the manifests
name, and every downstream call that passes `model` then fails with a confusing 404. This asks the
server directly rather than inferring from the manifest.

Usage:
    export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
    python scripts/probe_model.py
    python scripts/probe_model.py --expect qwen3-1.7b
"""

from __future__ import annotations

import argparse
import sys

import requests

from _cluster import ClusterError, die, port_forward

DEFAULT_SERVICE = "qwen3-predictor"
DEFAULT_NAMESPACE = "kserve"
DEFAULT_PORT = 80
DEFAULT_MODEL = "qwen3-1.7b"


def probe(base_url: str, timeout: int = 30) -> list[str]:
    """Return the model ids the server advertises."""
    res = requests.get(f"{base_url}/v1/models", timeout=timeout)
    res.raise_for_status()
    return [m.get("id", "") for m in res.json().get("data", [])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--expect", default=DEFAULT_MODEL,
                    help="model id that must be served; empty string to only list")
    args = ap.parse_args(argv)

    try:
        with port_forward(args.service, args.namespace, args.port) as base:
            served = probe(base)
    except ClusterError as exc:
        return die(str(exc))
    except requests.RequestException as exc:
        return die(f"could not reach {args.namespace}/{args.service}: {exc}")

    if not served:
        return die("the server advertised no models; the container is up but has loaded nothing")

    print(f"served models: {', '.join(served)}")
    if args.expect and args.expect not in served:
        return die(
            f"expected '{args.expect}' but the server serves {served}. Downstream calls that pass "
            f"model='{args.expect}' will 404 even though the InferenceService reports Ready."
        )
    if args.expect:
        print(f"OK: '{args.expect}' is served")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
