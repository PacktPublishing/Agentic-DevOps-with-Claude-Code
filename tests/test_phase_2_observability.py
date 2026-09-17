# ABOUTME: Phase 2 gate. Observability stack healthy, storage bound, the collector on
# ABOUTME: every node, Grafana datasources wired, and a trace reaching Tempo.
import time

import pytest
from conftest import assert_apps_healthy, get_json, incluster_curl, kubectl


def test_observability_apps_healthy():
    assert_apps_healthy(
        "kube-prometheus-stack", "loki", "tempo",
        "opentelemetry-operator", "opentelemetry-collector",
    )


def test_prometheus_and_alertmanager_pvcs_bound():
    obj = get_json("get", "pvc", "-n", "observability")
    relevant = [
        p for p in obj.get("items", [])
        if any(k in p["metadata"]["name"] for k in ("prometheus", "alertmanager"))
    ]
    assert relevant, "no Prometheus/Alertmanager PVCs found"
    for pvc in relevant:
        phase = pvc.get("status", {}).get("phase")
        assert phase == "Bound", f"{pvc['metadata']['name']} is {phase}, not Bound"


def test_collector_daemonset_ready_on_each_node():
    obj = get_json("get", "daemonset", "opentelemetry-collector-agent", "-n", "observability")
    status = obj.get("status", {})
    desired = status.get("desiredNumberScheduled", 0)
    ready = status.get("numberReady", 0)
    assert desired > 0 and ready == desired, f"collector ready {ready}/{desired}"


@pytest.mark.integration
def test_grafana_has_loki_and_tempo_datasources():
    pw = kubectl(
        "get", "secret", "-n", "observability", "-l", "app.kubernetes.io/name=grafana",
        "-o", "jsonpath={.items[0].data.admin-password}",
    ).stdout
    import base64
    password = base64.b64decode(pw).decode() if pw else ""
    # Pass credentials with -u, not embedded in the URL: a password with URL-special
    # characters silently breaks basic-auth and yields a 401. incluster_curl also appends
    # the http code and a kubectl "pod deleted" line, so the return is not clean JSON;
    # match the datasource types by substring rather than json.loads (which fails on the
    # suffix and returns an empty list even when the datasources are present).
    body = incluster_curl(
        "http://kube-prometheus-stack-grafana.observability.svc/api/datasources",
        "-u", "admin:%s" % password,
        ns="observability",
    )
    compact = body.replace(" ", "")
    assert '"type":"loki"' in compact and '"type":"tempo"' in compact, \
        f"loki/tempo datasources not found; body starts: {body[:300]}"


@pytest.mark.integration
def test_trace_reaches_tempo():
    # Push a minimal OTLP/HTTP trace through the collector, then search Tempo for it.
    # Stamp the span with the current time. A hardcoded startTimeUnixNano of 1 (1970) put
    # the span decades outside Tempo's default /api/search window, so it was stored but
    # never returned, and the test failed even though the trace pipeline was healthy.
    start_ns = time.time_ns()
    end_ns = start_ns + 1_000_000  # 1 ms span
    otlp = (
        '{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name",'
        '"value":{"stringValue":"phase2-probe"}}]},"scopeSpans":[{"spans":[{'
        '"traceId":"00000000000000000000000000abc123","spanId":"0000000000abc123",'
        '"name":"phase2-probe-span","kind":1,"startTimeUnixNano":"%d","endTimeUnixNano":"%d"}]}]}]}'
        % (start_ns, end_ns)
    )
    incluster_curl(
        "http://opentelemetry-collector.observability.svc:4318/v1/traces",
        "-X", "POST", "-H", "Content-Type: application/json", "--data", otlp,
        ns="observability",
    )
    # Tempo does not make a span searchable the instant it is received: it flows through the
    # distributor to an ingester before /api/search returns it. A single immediate query
    # misses it. Poll for it (found within ~5s live on a healthy 2.9.0 stack).
    found = ""
    for _ in range(8):
        time.sleep(5)
        found = incluster_curl(
            "http://tempo.observability.svc:3200/api/search",
            "--get", "--data-urlencode", 'q={ resource.service.name = "phase2-probe" }',
            ns="observability",
        )
        if "traceID" in found or "phase2-probe" in found:
            break
    assert "traceID" in found or "phase2-probe" in found, "probe trace not found in Tempo after retries"
