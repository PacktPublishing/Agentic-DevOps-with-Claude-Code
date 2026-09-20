#!/usr/bin/env python3
# ABOUTME: Shared cluster access for the probe and benchmark scripts: an explicit-kubeconfig
# ABOUTME: kubectl wrapper and a port-forward context manager, so no script touches the default context.
"""Cluster plumbing shared by the probe scripts.

Every script here reaches in-cluster Services the same way, for the same reason the phase tests
do: this machine is shared, so nothing may read or write the default kubeconfig. `KUBECONFIG_FILE`
must point at a dedicated file, and `EXPECTED_CONTEXT` is checked before any traffic, so a probe
cannot silently run against the wrong cluster.

Port-forwarding rather than a one-shot in-cluster curl pod, because the benchmark issues many
requests and a pod per request would measure pod startup rather than inference.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from typing import Iterator

KUBECONFIG_FILE = os.environ.get("KUBECONFIG_FILE", "")
EXPECTED_CONTEXT = os.environ.get("EXPECTED_CONTEXT", "")


class ClusterError(RuntimeError):
    """Raised when the cluster is unreachable or points somewhere unexpected."""


def _require_kubeconfig() -> str:
    if not KUBECONFIG_FILE:
        raise ClusterError(
            "KUBECONFIG_FILE is not set. These scripts never read the default kubeconfig: "
            "this machine is shared and other systems use kubectl. Pull credentials into a "
            "dedicated file first:\n"
            "  aws eks update-kubeconfig --name <cluster> --kubeconfig /tmp/<cluster>.kubeconfig\n"
            "  export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig"
        )
    if not os.path.exists(KUBECONFIG_FILE):
        raise ClusterError(f"KUBECONFIG_FILE points at a file that does not exist: {KUBECONFIG_FILE}")
    return KUBECONFIG_FILE


def kubectl(*args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run kubectl bound to the explicit kubeconfig."""
    kubeconfig = _require_kubeconfig()
    res = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if check and res.returncode != 0:
        raise ClusterError(f"kubectl {' '.join(args)} failed: {res.stderr.strip()}")
    return res


def get_json(*args: str) -> dict:
    return json.loads(kubectl(*args, "-o", "json").stdout)


def guard_context() -> str:
    """Confirm the kubeconfig points where the caller expects. Returns the context name."""
    ctx = kubectl("config", "current-context").stdout.strip()
    if EXPECTED_CONTEXT and EXPECTED_CONTEXT not in ctx:
        raise ClusterError(
            f"context '{ctx}' does not match EXPECTED_CONTEXT '{EXPECTED_CONTEXT}'. "
            "Refusing to send traffic to a cluster you did not name."
        )
    return ctx


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def port_forward(service: str, namespace: str, remote_port: int, timeout: float = 30.0) -> Iterator[str]:
    """Port-forward a Service and yield a http://127.0.0.1:<port> base URL.

    Waits for the local port to accept a connection before yielding. kubectl prints "Forwarding
    from ..." before the tunnel is actually usable, so trusting that line produces a connection
    refused on the first request and reads as the service being down.
    """
    guard_context()
    local = _free_port()
    proc = subprocess.Popen(
        ["kubectl", "--kubeconfig", _require_kubeconfig(), "port-forward",
         "-n", namespace, f"svc/{service}", f"{local}:{remote_port}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                err = (proc.stderr.read() or "").strip()
                raise ClusterError(f"port-forward to {namespace}/{service}:{remote_port} exited: {err}")
            with contextlib.suppress(OSError):
                with socket.create_connection(("127.0.0.1", local), timeout=1):
                    break
            time.sleep(0.25)
        else:
            raise ClusterError(
                f"port-forward to {namespace}/{service}:{remote_port} did not become ready in {timeout}s"
            )
        yield f"http://127.0.0.1:{local}"
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)


def die(message: str, code: int = 1) -> "int":
    print(f"error: {message}", file=sys.stderr)
    return code
