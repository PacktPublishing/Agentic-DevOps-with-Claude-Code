<!-- ABOUTME: The version-maintenance policy for this repo: what is frozen, what moves, and on what -->
<!-- ABOUTME: cadence, anchored to the Kubernetes release train rather than to calendar dates. -->

# Version maintenance

This repo has two audiences with opposite needs, so it has two policies.

| Where | Policy | For |
|---|---|---|
| Tag `v1.0.0` | Frozen. Never re-pinned. | Reproducing the 23 July 2026 build exactly as delivered |
| `main` | Maintained on the cadence below | Installing against a current cluster |

The freeze in `versions.lock.md` was written for a four-hour live event, where a version moving
under you mid-build is the worst thing that can happen. It was never meant to govern a repo people
read for years. Confusing the two is how a companion repo rots into something that no longer
installs.

## Cadence

Anchored to the **Kubernetes release train**, not the calendar: roughly three minors a year, about
15 weeks apart, each supported for about 14 months under the N-2 policy. Tying maintenance to the
thing that actually forces our hand beats picking arbitrary dates.

### Per Kubernetes minor (~15 weeks)

1. Raise `MIN_MINOR` in `tests/test_phase_0_preflight.py` as minors reach end of life.
2. Run the full phase suite against the newest supported minor.
3. Update the support matrix in the README.

Known dates, so the next few passes need no research:

| Minor | Released | End of life |
|---|---|---|
| 1.34 | | 2026-10-27 |
| 1.35 | | 2027-02-28 |
| 1.36 | | 2027-06-28 |
| 1.37 | 2026-08-26 | 2027-10-28 |

At each EOL, raise the floor to the next minor. Do **not** convert the floor back into an
allow-list of exact versions: that is the defect that broke the gate on the day 1.37 shipped, and
`tests/test_version_gate.py` now fails the build if anyone reintroduces it.

### Monthly

- **vLLM.** Ships fast. Bump to the current CPU image, then re-run `inference_probe.py` and
  `benchmark_inference.py`. Re-verify the `--device=cpu` rejection, `VLLM_CPU_KVCACHE_SPACE`,
  `SYS_NICE`, and the hermes tool parser, since those are the settings that break silently.
- **kagent and agentgateway.** Both ship breaking CRD changes on minor releases. Read the changelog
  for schema changes before bumping, not after.

### Quarterly

Re-pin: Argo CD chart, kube-prometheus-stack, Tempo, Loki, cert-manager, Gateway API / kgateway,
Backstage, External Secrets, Kyverno.

Two standing checks:

- **Argo CD.** From 3.5 onward it renders Helm with the **v4 binary**. Re-test every chart render
  after that jump; it is the bump most likely to surface unrelated breakage.
- **Tempo.** The 2.9.0 pin is a deliberate downgrade, not neglect, and the tracking issue is a
  trap. [grafana/tempo#6436](https://github.com/grafana/tempo/issues/6436) is **closed**, but it was
  closed by the reporter fixing their own configuration rather than by a Tempo fix, so its state
  says nothing about whether 2.10 works here. What justifies the pin is this repo's own measurement
  on 2026-07-23: on 2.10 a trace written then queried came back empty and the phase test failed.
  Lift it only when that test passes on a current 2.10 build. Do not lift it because the issue went
  green.

### Event-driven

- **MCP spec revision.** Reconcile `RemoteMCPServer` and the agentgateway MCP route. Revisions have
  removed protocol-level sessions and the initialize handshake, so these are not cosmetic.
- **Claude Code settings schema.** Re-validate `.claude/` when it changes.

### Continuous

- **LLM Guard.** Effectively frozen upstream. Watch for CVEs, and keep a maintained replacement
  scanner pre-selected so a swap is a decision already made rather than an emergency.

## The automation

`scripts/version_sweep.py` compares every pin against upstream: Helm index files for charts, the
GitHub releases API for the rest, pre-releases excluded. `.github/workflows/version-sweep.yml` runs
it on the 1st of each month and opens an issue with the table.

It **does not fail on drift**, on purpose. This platform pins deliberately and holds two pins for
measured reasons, so a job that went red every month would be ignored within two months and then
mean nothing. Making drift visible is the job; deciding what to do about it is a person's.

Held pins are reported separately with their reason attached, and that includes ones with no
upstream release at all: llm-guard is archived, so the releases API returns nothing, and letting it
fall into an "unresolved" bucket would bury the note that matters most about it.

## After a pin moves, regenerate the lock

`components.yaml` is the source of truth; `versions.lock.md` is the human lookup, and Chapter 2
tells readers to keep the two in step. Editing a pin and stopping there breaks that in the one
document a reader consults to check it.

```bash
python3 scripts/gen-versions-lock.py           # rewrite the table
python3 scripts/gen-versions-lock.py --check   # exit 1 if it is stale
```

Only the component table is generated. Every other section of the lock file is written by hand and
is left alone.

`tests/test_versions_lock.py` fails when the two disagree, so CI catches a forgotten regeneration on
the push rather than a reader catching it months later. That is not hypothetical: the 10 September
migration moved 23 pins and left the lock untouched, and the two files then disagreed on 21 of 31
rows while still advertising Score, which had been removed. It was found by reading the file.

Each component carries a `display_name` for the table. Without one the generator falls back to the
kebab-case identifier and `AWS Load Balancer Controller` silently becomes
`aws-load-balancer-controller`; a test covers that too.

## The current survey

[`version-drift-2026-09.md`](version-drift-2026-09.md) records how far every pin had drifted as of
2026-09-05, measured against upstream rather than read off a report, with a suggested order for
moving them and the three findings that are not just numbers.

## What "verified" means here

A version bump is not done when the number changes. It is done when the phase suite passes against
it. A pinned version that nobody has run is a guess with a decimal point in it.
