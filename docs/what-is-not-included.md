<!-- ABOUTME: What was removed from this repository before publication, and why. -->
<!-- ABOUTME: A reader who finds a dangling reference should find the answer here. -->

# What is not included, and why

This platform was built live, in front of an audience, on a fleet of 250 clusters provisioned for a
single afternoon. A lot of what made that possible has nothing to do with running the platform, and
shipping it would have meant handing you a repository where most of the files were about an event
you were not at.

What follows is the full list, so that a reference you find dangling has an answer rather than
looking like rot.

## Provisioning and fleet automation

Terraform for the lab VPC and the cluster, the driver that stamped out 250 of them across five AWS
accounts, the tag audit, the orphan sweep, and the credential distribution app.

It is specific to one AWS organisation and one event. Anything in here that depends on it says so at
the point of dependency, and the only one that matters is the AWS Load Balancer Controller's
`clusterName` and `vpcId`, which a provisioning step substitutes. Set them yourself and the platform
syncs.

## The browser terminal

A containerised multi-tab workbench served to each attendee over the web. It exists so that 250
people could reach a shell without installing anything, which is not a problem you have.

**It also has no authentication**, which is why it would not have shipped in any case. Every
terminal was served at a predictable public URL and each was a `sudo`-capable cluster-admin shell.

## Delivery material

The run-of-show, the preflight and failure-recovery checklists, the copy-paste command file, the
catch-up guide for people joining late, the defect log from the live run, the fleet lessons log, and
the build specification that produced all of it.

These are about delivering a workshop: what to say, in what order, and what to do when a beat fails
on camera. The platform decisions that came out of that work are in `architecture.md` and
`reference/decisions.md`, which are written for someone building rather than presenting.

## What was kept, and might surprise you

**`spec/`** stays. The nine phase specifications are what the platform is checked against, and
`tests/` is named for them. They describe a system, not a performance.

**`reference/decisions.md`** stays, including entries about fleet scale. A decision is worth more
with its reasoning attached, and "we chose Pod Identity over IRSA because 300 per-cluster OIDC trust
policies is not a thing anyone should maintain" is useful even if you are building one cluster.
Entries that name removed files are history, not instructions.

**The agent configuration** in `.claude/` stays: the permission policy and the audit hook. Those are
subject matter, not stagecraft.

## Verifying this yourself

Nothing here is a matter of trust. The repository contains no credentials, and nothing in it names a
real AWS account. Both are checked rather than asserted:

```bash
# Tracked files only. A plain `grep -r` also walks gitignored build output and local scratch,
# which is not what ships, and it will give you a misleading answer.
git ls-files -z | xargs -0 grep -lE "AKIA[0-9A-Z]{16}|aws_secret_access_key"   # no access keys
git ls-files -z | xargs -0 grep -hPo "(?<![0-9A-Za-z])[0-9]{12}(?![0-9A-Za-z])" | sort -u   # no account ids
```

The second returns one match, `000000000000`, which is a fabricated trace id in
`tests/test_phase_2_observability.py` and not an account.

The two passwords you will find are `Workshop-Dev-Only1!` on the in-cluster Gitea and
`sk-local-vllm-not-a-real-key` on the demo agent. Neither guards anything outside the cluster, and
the second is not a key at all: the in-cluster vLLM requires no authentication and simply expects
the OpenAI client to send the header.
