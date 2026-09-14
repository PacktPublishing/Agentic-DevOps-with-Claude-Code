# ABOUTME: Asserts every repo path a tracked file points at actually exists in the tree.
# ABOUTME: A doc that cites a deleted file reads as rot, and a reader cannot tell rot from a bug.
#
# When the live event was stripped out of this tree, the files that described it went but the
# references to them did not. The agent memory alone pointed at eight paths that no longer existed,
# including the build spec it told a reader to start from and the test file it told an agent to run.
# Each one was found by hand. This finds them all.
#
# This is a tip-only check. Documentation ships early and legitimately cites files that later
# chapters add, so at any chapter tag before the last one it reports forward references that do
# resolve at the tip. CI runs it against the full tree. Do not weaken it to pass at a chapter tag.
#
# Only three syntaxes are considered, because a bare token scan reports hundreds of Kubernetes API
# groups and label keys as if they were paths:
#   1. backtick spans, which is how this repo cites files everywhere, including inside YAML comments
#   2. Markdown link targets
#   3. os.path.join(REPO_ROOT, ...) literals in Python, parsed rather than matched
import ast
import os
import re
import subprocess

from conftest import REPO_ROOT

BACKTICK = re.compile(r"`([^`\n]+)`")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")

# A reference is only considered when its first segment names something real at the top of the tree.
# That one rule removes apps/v1, gateway.networking.k8s.io/v1, app.kubernetes.io/name,
# actions/checkout, Qwen/Qwen3-1.7B, ghcr.io/... and every Helm repo URL, with no allow-list.
def _top_level():
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True,
                         check=True, text=True).stdout.split("\n")
    return {p.split("/")[0] for p in out if p}


ALLOWED = {
    # platform/ is the reader's working copy. It deliberately does not exist until they create it,
    # and every Application under solution/ resolves its paths inside the in-cluster Git repository
    # rather than inside this one.
    "platform",
}

# Files whose citations are about somewhere other than this repository.
ALLOWED_FILES = {
    # The left column is the name the book prints, which is the whole point of the mapping.
    "docs/book-name-mapping.md",
    # A scaffolder skeleton. Its paths are inside the repository the template generates.
    "solution/platform/3-self-service/agent-service/skeleton/README.md",
    # Cites Claude Code's own configuration surface, not paths in this tree.
    "docs/reference/research-findings-june-2026.md",
}

# Paths that exist only at runtime.
ALLOWED_REFS = {
    ".claude/audit/tool-invocations.jsonl",
}


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True,
                         check=True, text=True).stdout.split("\n")
    files = {p for p in out if p}
    dirs = set()
    for p in files:
        parts = p.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return files | dirs


def _candidates(name, text):
    """Yield (lineno, reference) for every path-shaped citation in one file."""
    for lineno, line in enumerate(text.split("\n"), 1):
        for m in BACKTICK.finditer(line):
            yield lineno, m.group(1)
        for m in MD_LINK.finditer(line):
            yield lineno, m.group(1)
    if name.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr == "join"):
                continue
            args = node.args
            if not args or not (isinstance(args[0], ast.Name) and args[0].id == "REPO_ROOT"):
                continue
            parts = [a.value for a in args[1:] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if len(parts) == len(args) - 1 and parts:
                yield getattr(node, "lineno", 0), "/".join(parts)


def _normalise(ref, referring_file):
    ref = ref.strip().split("#")[0].split("::")[0].rstrip(".,;:")
    if not ref or ref.startswith(("http://", "https://", "mailto:")):
        return None
    # Commands in this repo are written to be run from the repo root, so a leading ./ is
    # root-relative. A ../ in a Markdown link really is relative to the file that carries it.
    if ref.startswith("./"):
        ref = ref[2:]
    elif ref.startswith("../"):
        base = os.path.dirname(referring_file)
        ref = os.path.normpath(os.path.join(base, ref))
    return ref.rstrip("/") or None


def test_every_path_a_tracked_file_cites_exists():
    tracked, tops = _tracked(), _top_level()
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                             capture_output=True, check=True).stdout
    offenders = {}
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
        text = raw.decode("utf-8", errors="ignore")
        if name in ALLOWED_FILES:
            continue
        for lineno, ref in _candidates(name, text):
            norm = _normalise(ref, name)
            if not norm or norm in ALLOWED_REFS:
                continue
            first = norm.split("/")[0]
            if first not in tops or first in ALLOWED:
                continue
            if "/" not in norm and not os.path.splitext(norm)[1]:
                continue  # a bare top-level word, not a path
            if norm in tracked:
                continue
            # A glob resolves when anything matches it. N is a placeholder this repo uses for a
            # phase number, as in spec/phases/phase-N-*.md, so it counts as a wildcard too.
            if any(ch in norm for ch in "*?") or re.search(r"-N-|<[a-z]+>", norm):
                # Build the pattern from the literal segments, so nothing has to be un-escaped.
                pat = re.escape(norm)
                for literal, expansion in (
                    (re.escape("**"), ".*"),
                    (re.escape("*"), "[^/]*"),
                    (re.escape("?"), "."),
                    (re.escape("-N-"), "-[0-9]-"),
                ):
                    pat = pat.replace(literal, expansion)
                pat = re.sub(r"<[\\w\\-]+?>", "[^/]+", pat)
                if any(re.fullmatch(pat, t) for t in tracked):
                    continue
            offenders[f"{name}:{lineno} -> {norm}"] = norm
    assert not offenders, (
        "tracked files cite paths that do not exist:\n"
        + "\n".join(f"    {k}" for k in sorted(offenders))
    )
