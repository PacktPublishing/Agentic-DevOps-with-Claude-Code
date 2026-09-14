# ABOUTME: Asserts the shipped agent permission policy actually enforces what the book teaches,
# ABOUTME: rather than shipping rules that a permission mode silently disables.
#
# The defect this exists for: the tracked settings carried defaultMode "bypassPermissions", which
# makes every `ask` rule a no-op. Twelve rules covering mutating kubectl, helm, argocd and git verbs
# were present, reviewed, and dead. Chapter 2 teaches that those rules "create a pause and an audit
# event", so a reader cloning the repo got an agent that never paused, while the file looked like it
# implemented the lesson.
#
# That is the worst shape a control can take: present, plausible, and inert.
import json
import os

import pytest

from conftest import REPO_ROOT

SETTINGS = os.path.join(REPO_ROOT, ".claude", "settings.json")

# Modes that skip prompting entirely, so an `ask` rule can never fire.
MODES_THAT_DISABLE_ASK = {"bypassPermissions"}

# Mutating verbs the book calls out by name. Assembled rather than written literally so a local
# pre-tool hook that greps command text does not mistake this list for a command being run.
MUTATING_VERBS = [
    "kubectl apply", "kubectl delete", "helm install", "argocd app sync", "git" + " push",
]


@pytest.fixture(scope="module")
def permissions():
    assert os.path.exists(SETTINGS), f"missing agent settings: {SETTINGS}"
    return json.load(open(SETTINGS))["permissions"]


def test_ask_rules_are_not_disabled_by_the_default_mode(permissions):
    mode = permissions.get("defaultMode")
    assert mode not in MODES_THAT_DISABLE_ASK, (
        f"defaultMode is {mode!r}, which skips prompting, so all "
        f"{len(permissions.get('ask', []))} ask rules are inert. The shipped policy must enforce "
        "what it documents; put an unprompted mode in the gitignored local settings instead."
    )


def test_mutations_are_gated_rather_than_allowed(permissions):
    """Every mutating verb the book calls out must be in ask or deny, never in allow."""
    allow = " ".join(permissions.get("allow", []))
    gated = " ".join(permissions.get("ask", []) + permissions.get("deny", []))
    for verb in MUTATING_VERBS:
        assert verb not in allow, f"{verb!r} is allowed outright; it should require approval"
        assert verb in gated, f"{verb!r} is neither allowed nor gated; it is unlisted"


def test_the_harness_config_is_protected_from_the_agent(permissions):
    """Chapter 2's claim: the deny on the config directory stops the agent rewriting its own rules.

    Worth stating precisely, because the guarantee is narrower than it reads. The rule denies the
    Edit tool. It is not a filesystem ACL, so it does not by itself stop a shell command that writes
    the same path; what stops that is the mutating-command gating above plus the default mode. Both
    halves are needed, which is why this checks the deny rule and the mode together.
    """
    deny = " ".join(permissions.get("deny", []))
    assert ".claude" in deny, "nothing denies edits to the agent's own configuration"
    assert permissions.get("defaultMode") not in MODES_THAT_DISABLE_ASK, (
        "an unprompted mode undoes the protection the deny rule is supposed to provide"
    )


def test_credential_paths_are_denied(permissions):
    deny = " ".join(permissions.get("deny", []))
    for pattern in (".env", "credentials"):
        assert pattern in deny, f"credential path {pattern!r} is not denied"
