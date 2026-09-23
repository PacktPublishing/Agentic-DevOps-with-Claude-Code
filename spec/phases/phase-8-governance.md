# Phase 8: Governance and attribution (chapter 10)

**Goal:** Flip the AI-plane policies from audit to enforce with a live denial, show per-agent attribution in Loki, and close with the 30-day commitment.

**Inputs:** All prior phases complete. The AI-plane Kyverno policies defined in audit mode in Phase 4. The audit hook shipping agent tool-invocation logs to Loki.

**Outputs:**
- The AI-plane Kyverno policies flipped from Audit to Enforce
- A live denial: an attempt to apply a violating agent manifest (for example an agent with no LLM Guard policy reference, or an image outside the allowlist) is blocked by Kyverno at admission
- A Loki query showing every action attributed to a named agent identity, including the building agent's own session via the audit hook
- One specific change you intend to make in your own platform within 30 days, written down

**Test criteria (tests/test_phase_8_governance.py):**
- The AI-plane policies are in Enforce mode
- A known violating agent manifest is denied by Kyverno (admission rejected)
- A known-good agent manifest is admitted
- A Loki query returns tool-invocation entries labeled with an agent identity

**Completion promise:** `<promise>PHASE8_DONE</promise>` and, when all phases pass, `<promise>ALL_PHASES_COMPLETE</promise>`

**Key decisions:**
- Policies are CEL-based Kyverno types; the ValidatingPolicy converts to a native ValidatingAdmissionPolicy. The denial demonstration is the one sanctioned use of mutating kubectl.
- The denial is deterministic: the violating fixture lives in the repo, and the reset script restores known-good policy state.
- Attribution covers the building agent itself, the point of the beat: the agent that built the platform appears in the platform's own audit trail.

**Stop here.** This is the final phase. Output both promises only when every phase test passes.
