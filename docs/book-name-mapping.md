<!-- ABOUTME: Maps the names the book prints to the files in this repository, where they differ. -->
<!-- ABOUTME: Reconciled against the final chapter text on 2026-09-23 by extracting every path it names. -->

# Book-to-repo name mapping

If the book names a file and you cannot find it, look here first.

Most names agree. Where they do not, the **repo name is canonical**, because the repo's test files
are aligned to `spec/phases/phase-N-*.md` so that a reader working phase by phase runs the test whose
number matches the phase they are on. Renaming them to match the book would break that alignment,
which is structural; the mapping below is one table.

This was reconciled by extracting every `test_*.py`, `scripts/*`, and `fixtures/*` reference from the
final chapter text and checking each against the tree. The counts below are how many times each name
appears in the book.

## Tests

### Names that agree

`test_phase_0_preflight.py`, `test_phase_1_foundation.py`, `test_phase_2_observability.py`,
`test_phase_3_portal.py` and `test_inventory_summary.py` are named by the book and present here under
exactly those names. Nothing to do.

### Names to correct in the book

| Book prints | Times | Repo file | Why it differs |
|---|---|---|---|
| `test_gateway_contract.py` | 3 | `tests/test_phase_4_ai_gateway.py` | The gateway assertions are the phase gate, not a separate contract file |
| `test_phase_4_runtime.py` | 1 | `tests/test_phase_4_ai_gateway.py` | Phase 4 is the gateway plane; the runtime is phase 5 |
| `test_agent_ready.py` | 3 | `tests/test_phase_5_agent_runtime.py` | Named for the phase, not for the condition it waits on |
| `test_mcp_contract.py` | 1 | `tests/test_phase_5_agent_runtime.py` | The MCP assertions live with the agent runtime that exercises them |
| `test_phase_6_serving.py` | 3 | `tests/test_phase_6_model_serving.py` | The phase is called model serving |
| `test_observability.py` | 1 | `tests/test_phase_2_observability.py` | Asserted at the phase where the plane is built |
| `test_golden_path.py` | 1 | `tests/test_phase_7_self_service.py` | The golden path is what phase 7 delivers |

Two of those, `test_gateway_contract.py` and `test_mcp_contract.py`, have no single counterpart
because their assertions were merged into the phase file. Splitting them back out would create files
that duplicate a phase gate, so the book should cite the phase test.

### `test_contract.py` is not in this repository, and should not be

Chapter 9 names `tests/test_contract.py` twice. It is not one of this repo's tests. It is a file in
the repository the scaffolder **generates**, and it ships as part of the template skeleton at
`solution/platform/3-self-service/agent-service/skeleton/tests/test_contract.py`. A reader looking
for it at the repo root will not find it, which is the confusion this row exists to prevent.

## The chapter 2 lab

Chapter 2 has you write a phase contract and run it. The chapter supplies the contract itself and
expects the rest to be here:

| File | Where it comes from |
|---|---|
| `spec/phases/example-inventory.md` | **You write it.** The chapter prints the complete file. It is deliberately not in this repo, because writing it is the exercise |
| `fixtures/device-inventory.json` | Here. The approved read-only source, entirely synthetic, using RFC 5737 documentation addresses |
| `schemas/inventory-summary.json` | Here. The contract the generated summary is validated against |
| `tests/test_inventory_summary.py` | Here. Three tests, one per line of the phase's test criteria |
| `out/inventory-summary.json` | Your agent generates it. Gitignored |

`tests/test_inventory_summary.py` is the only test here that is meant to fail on a fresh checkout,
because step 1 of the lab is running it and watching it fail for the right reason. It is excluded
from a bare `pytest` so it does not make every other run look broken. Run it the way the chapter
prints it:

```bash
python -m pytest tests/test_inventory_summary.py -q
```

Before the phase runs you get one failure and two skips. After it, three passes.

## The generated service contract

Chapter 9 lists six files the generated repository contains. All six are in the skeleton, so the
scaffolder emits them:

`catalog-info.yaml`, `manifests/agent.yaml`, `manifests/httproute.yaml`,
`manifests/kustomization.yaml`, `tests/test_contract.py`, `README.md`.

The chapter also installs `tests/requirements.txt` before running the contract tests, which ships
alongside them. The contract test has four tests, matching the "4 passed" the chapter prints.

## Scripts

Every script the book names is present. Six were added in response to the book naming them.

| Book names | Status |
|---|---|
| `scripts/check_components.py` | Present, with `scripts/test_check_components.py` |
| `probe_model.py` | Added. Asks `/v1/models` what is actually served and compares it to the expected id |
| `inference_probe.py` | Added. Sends a real completion, so "Ready" and "answers" are separate claims |
| `benchmark_inference.py` | Added. Sequential latency percentiles, with the cold first request reported separately |
| `trace_probe.py` | Added. Distinguishes no traces at all from traces missing `gen_ai.*` attributes |
| `verify_audit_event.py` | Added. Counts audit lines and how many are attributable |
| `requirements-trace.txt` | Added. The probe scripts' dependency |

Shared plumbing is in `scripts/_cluster.py`; the pure logic is covered by `scripts/test_probes.py`,
which needs no cluster.

## Fixtures

The book names four fixture paths. This repo puts fixtures **beside the component they exercise**, as
a sibling of `manifests/`, because each Application syncs `manifests/` only and a fixture that exists
to be rejected must never be reconciled.

| Book prints | Repo file |
|---|---|
| `fixtures/missing-guardrail.yaml`, `tests/fixtures/agent-missing-owner.yaml` | `solution/platform/2-ai-plane/ai-policies/fixtures/violating-agent.yaml` |
| `tests/fixtures/agent-known-good.yaml` | `solution/platform/2-ai-plane/ai-policies/fixtures/known-good-agent.yaml` |
| `fixtures/injection-fixture.yaml` | `solution/platform/2-ai-plane/llm-guard/fixtures/injection-fixture.yaml` |

`fixtures/device-inventory.json` is the exception and is exactly where the book says, because the
chapter 2 lab is not a platform component.

Three more fixtures exist that the book does not cite, one per AI policy:
`violating-endpoint.yaml`, `violating-otel.yaml`, `violating-image.yaml`.

## Tags

The book prints `checkpoint/module-1-end` in chapter 2. The checkpoint tags keep those names for
that reason, even though the rest of the repository now speaks in chapters rather than modules.

## Tests present here that the book does not cite

`test_phase_8_governance.py`, `test_platform_contract.py`, `test_version_gate.py`,
`test_agentgateway_manifests.py`, `test_argocd_health_checks.py`, `test_vendored_charts.py`,
`test_versions_lock.py`, `test_agent_permissions.py`, `test_conftest_helpers.py`,
`test_no_account_ids.py`, `test_no_leaked_context.py`, `test_no_dangling_paths.py`.

The last three are publication guards rather than platform tests: they assert this repository carries
no credentials, nothing belonging to anyone else, and no citation of a file that is not here.
