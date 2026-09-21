#!/usr/bin/env python3
# ABOUTME: End-to-end inference check: a real chat completion against the served model, asserting
# ABOUTME: the response echoes the served model id and actually contains generated tokens.
"""Probe inference, not just readiness.

`kubectl get inferenceservice` reporting Ready means the pod passed its probes. It does not mean
the model answers. On CPU the two come apart routinely: the container is up and the weights are
still loading, so the endpoint accepts connections and every completion times out. This sends a
real completion and reads the response.

Checks, in the order they fail usefully:
  1. the endpoint answers at all
  2. the response names the model that was requested, not a different one
  3. the response carries generated content and a token count above zero

Usage:
    export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
    python scripts/inference_probe.py
    python scripts/inference_probe.py --prompt "name three CNCF projects" --max-tokens 64
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import requests

from _cluster import ClusterError, die, port_forward

DEFAULT_SERVICE = "qwen3-predictor"
DEFAULT_NAMESPACE = "kserve"
DEFAULT_PORT = 80
DEFAULT_MODEL = "qwen3-1.7b"


def complete(base_url: str, model: str, prompt: str, max_tokens: int, timeout: int) -> tuple[dict, float]:
    """Send one chat completion. Returns (payload, elapsed_seconds)."""
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
    return res.json(), elapsed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prompt", default="Reply with the single word: ready")
    ap.add_argument("--max-tokens", type=int, default=16)
    ap.add_argument("--timeout", type=int, default=180,
                    help="seconds; generous because first-token latency on CPU is slow")
    args = ap.parse_args(argv)

    try:
        with port_forward(args.service, args.namespace, args.port) as base:
            payload, elapsed = complete(base, args.model, args.prompt, args.max_tokens, args.timeout)
    except ClusterError as exc:
        return die(str(exc))
    except requests.Timeout:
        return die(
            f"no completion within {args.timeout}s. On CPU this usually means the weights are still "
            "loading: the pod is Ready because its probes pass, while the model is not resident yet. "
            "Check the predictor logs for a 'Starting vLLM' / model-load line before assuming failure."
        )
    except requests.RequestException as exc:
        return die(f"inference request failed: {exc}")

    served = payload.get("model")
    if served != args.model:
        return die(f"requested model '{args.model}' but the response names '{served}'")

    choices = payload.get("choices") or []
    content = (choices[0].get("message", {}).get("content") if choices else "") or ""
    usage = payload.get("usage") or {}
    completion_tokens = usage.get("completion_tokens", 0)

    if not content.strip():
        return die("the response contained no content; the model answered with an empty string")
    if completion_tokens <= 0:
        return die(f"usage reports {completion_tokens} completion tokens; nothing was generated")

    print(f"model:      {served}")
    print(f"latency:    {elapsed:.2f}s")
    print(f"tokens:     {usage.get('prompt_tokens', '?')} prompt / {completion_tokens} completion")
    print(f"content:    {content.strip()[:200]}")
    print("OK: the served model answered with generated content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
