# ABOUTME: Asserts the published tree names no third party, no private link and no internal scheme.
# ABOUTME: This repository accompanies a book; it must not carry traces of how it was produced.
#
# The tree this repository was cut from had been used to deliver a live event, and the first pass at
# publishing it carried a great deal of that along: an operations runbook for the hosting platform
# with live service URLs, a decision log naming two unrelated client engagements and documenting a
# history rewrite, a share link to a private drive, and twenty-five internal identifiers keyed to a
# document that does not exist here. None of it was secret. All of it was somebody's business rather
# than the reader's, and none of it was caught by any test.
#
# These checks run against tracked files only, like tests/test_no_account_ids.py, because a
# recursive scan also walks build output and local scratch and reports things that do not ship.
import re
import subprocess

from conftest import REPO_ROOT

# Each pattern below names something that must not appear. Where a file legitimately contains one,
# it is allow-listed here by path with the reason, rather than by weakening the pattern.

# The file that documents what was excluded has to be able to say what it excluded, and the file
# that defines these rules has to be able to state them.
_DOC_EXEMPT = {"docs/what-is-not-included.md", "AGENTS.md", "tests/test_no_leaked_context.py"}

CHECKS = [
    (
        "third parties and other engagements",
        re.compile(r"\b(KCD|Unleash(ed)?|Unleash_an_Agent\w*|watchitburn|adwc-dev|packt-podid-val)\b", re.I),
        set(),
    ),
    (
        "personal and event domains",
        re.compile(r"(michaelrishiforrester|performantpro|ai-enhanced-devops)\.com|\bstudent\d+\."),
        set(),
    ),
    (
        "links to private shares",
        re.compile(r"(drive|docs)\.google\.com|dropbox\.com|notion\.so|[?&]usp=(sharing|drive_link)"),
        set(),
    ),
    (
        "internal identifier schemes with no key in this repository",
        re.compile(r"\((B\d{2}(/P\d{2})?)\)"),
        set(),
    ),
    (
        "references to directories that were removed",
        # internal/ and prds/ are anchored so a Go package path such as
        # go/core/internal/controller/... does not read as a reference to the removed directory.
        re.compile(r"\b(docs/fleet|scripts/provision/(fleet|vtt|router|distribution|lab-vpc|instructor)"
                   r"|docs/runbook|images/web-terminal|docs/reference/build-spec\.md"
                   r"|test_fleet_contract)|(?<![\w/])(internal|prds)/"),
        _DOC_EXEMPT,
    ),
    (
        "cloud resource identifiers",
        re.compile(r"\b(vol|i|vpc|subnet|sg|eipalloc)-[0-9a-f]{8,}\b|arn:aws:(iam|sts)::"),
        set(),
    ),
    (
        "delivery and presentation vocabulary",
        re.compile(r"\b(rehears\w*|run.of.show|backup (video|recording)|OBS scenes?|presenter)\b", re.I),
        _DOC_EXEMPT,
    ),
]

# An address in a published repository is either an example or somebody's real inbox.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
EMAIL_ALLOWED = re.compile(r"@(example\.(com|org)|users\.noreply\.github\.com|platform\.local)\b")

# Paths that should never be tracked at all, matched on the name rather than the contents.
STRAY_PATHS = re.compile(r"\.tmp\.|\.orig$|\.rej$|\.bak$|\.DS_Store$|settings\.local\.json|linkedin|headshot")


def _tracked_text_files():
    """Yield (repo-relative path, text) for every tracked file that is not binary."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout
    for name in listing.decode().split("\0"):
        if not name:
            continue
        try:
            with open(f"{REPO_ROOT}/{name}", "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            continue
        if b"\0" in raw:
            continue
        yield name, raw.decode("utf-8", errors="ignore")


# This file necessarily contains every pattern it forbids, so it never scans itself. It became
# tracked at its first commit, which is the moment it started matching its own definitions.
_SELF = "tests/test_no_leaked_context.py"


def _offenders(pattern, exempt):
    found = {}
    for name, text in _tracked_text_files():
        if name == _SELF or name in exempt:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            m = pattern.search(line)
            if m:
                found.setdefault(f"{name}:{lineno}", m.group(0))
    return found


def test_the_tree_names_nothing_it_should_not():
    failures = {}
    for label, pattern, exempt in CHECKS:
        hits = _offenders(pattern, exempt)
        if hits:
            failures[label] = hits
    assert not failures, (
        "the published tree carries material that belongs to somebody else:\n"
        + "\n".join(
            f"  {label}:\n"
            + "\n".join(f"    {where}  ->  {what!r}" for where, what in sorted(hits.items()))
            for label, hits in failures.items()
        )
    )


def test_no_real_email_addresses_are_tracked():
    offenders = {}
    for name, text in _tracked_text_files():
        if name in _DOC_EXEMPT:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            for m in EMAIL.finditer(line):
                if not EMAIL_ALLOWED.search(m.group(0)):
                    offenders[f"{name}:{lineno}"] = m.group(0)
    assert not offenders, (
        "email addresses that are not example addresses: "
        + ", ".join(f"{k} -> {v}" for k, v in sorted(offenders.items()))
    )


def test_no_stray_or_local_files_are_tracked():
    listing = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, check=True, text=True
    ).stdout.split("\n")
    offenders = sorted(p for p in listing if p and STRAY_PATHS.search(p))
    assert not offenders, f"editor leftovers or local-only files are tracked: {offenders}"
