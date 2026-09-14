# Phase gate tests

One file per build phase. Each asserts the phase's spec test criteria against a live
cluster. Run them as the gate at the end of each phase.

## Running

All cluster access uses an explicit kubeconfig and verifies the context first (never the
shared default). Set both:

```bash
export KUBECONFIG_FILE=/tmp/<cluster>.kubeconfig
export EXPECTED_CONTEXT=<substring of the cluster context, e.g. adwc>
uv run --with pytest --with pyyaml python -m pytest tests/ -q
```

Without `KUBECONFIG_FILE`, the cluster-dependent tests skip (only the components-pinned
check in phase 0 runs). If the current context does not contain `EXPECTED_CONTEXT`, the
run aborts before touching anything.

## If you checked out a chapter tag

`chapter-01` through `chapter-10` give you the tree as of that chapter, which means an
unfinished platform. A bare `pytest` there will report failures, and they are not defects:
some tests in this directory are whole-tree invariants rather than phase gates, and they
assert over components that later chapters add. `test_agentgateway_manifests.py`, for
instance, refuses to pass without at least one Agent manifest to check, which is
deliberate, because a test that silently passes over an empty set is worse than no test.

The gate for a chapter is its own phase file. Chapter N runs phase N minus 2:

```bash
pytest tests/test_phase_4_ai_gateway.py -q     # the chapter 6 gate
```

Those are present and runnable at every chapter tag. Run the whole suite at the tip.

## Markers

Tests tagged `integration` need a fully built cluster and in-cluster traffic (a trace
reaching Tempo, an injection blocked at agentgateway, a golden-path run). Skip them for a
fast structural gate:

```bash
uv run --with pytest python -m pytest tests/ -m "not integration" -q
```

## Note

A few integration checks assume response contracts (the agentgateway audit log, the
agent route path, the Loki agent-identity label) that should be confirmed against the
live deployment before the freeze; they are marked and commented in place.
