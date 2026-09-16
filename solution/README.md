# solution/: the reference build

This is the finished, battle-hardened platform: the manifests, all pinned and
already debugged, that the workshop's build produces. It is the **reference**,
not your starting point.

The workshop asks you to build the platform yourself, from the spec in
`spec/BUILD-SPEC.md` and the per-phase files in `spec/phases/`. Your agent
generates the manifests into `platform/` and deploys them through Git. That is
the point of the workshop: watch the agent build a real platform.

Come here only when you are stuck, or to compare. Each phase's catch-up path is:

```
# bring in the reference for the phase you are on, then let ArgoCD sync it
cp -a solution/platform/. platform/
git add -A && git commit -m "reference build"
# apply the App-of-Apps and diff against what you generated
```

`solution/platform/` mirrors the `platform/` layout exactly (`0-bootstrap`,
`1-foundation`, `2-ai-plane`, `3-self-service`), and the ArgoCD Applications
inside point at `platform/…`, so a copy into your `platform/` works as-is.

One step is not optional. The AWS Load Balancer Controller manifest ships with
`REPLACE_WITH_CLUSTER_NAME`, `REPLACE_WITH_VPC_ID` and `REPLACE_WITH_REGION`,
because none of the three can be hardcoded in a reference build. Run
`./provision/cluster-facts.sh` after copying. It fills all three into
`platform/` from your Terraform outputs and leaves `solution/` alone. A
placeholder that survives leaves the Application Degraded forever while ArgoCD
reports the sync succeeded, so the script re-checks and fails loudly instead.

If you copy the whole thing and never build, you will still end up with a
working platform. But the build is the point. Reach for `solution/` when you
need it, not before.
