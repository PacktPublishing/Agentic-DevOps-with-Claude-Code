# ABOUTME: Asserts the tracked tree carries no real AWS account id and no access key.
# ABOUTME: docs/what-is-not-included.md promises a reader exactly this; here it is as a test.
#
# The promise was broken once, silently. The commit that stripped the live event from this branch
# also deleted seven nested .gitignore files, because they sat in the provisioning directories it
# was removing. That left 1,068 run logs on disk with nothing ignoring them, and the next commit
# staged the whole tree and took all of them in: five real AWS account ids, roughly twenty thousand
# occurrences, on a public branch destined for a publisher's repository. The suite was green
# throughout, because no test read the tracked file list.
#
# These are the two commands docs/what-is-not-included.md tells a reader to run, so the document
# and the suite cannot drift apart. Both scan tracked files only: a plain recursive grep walks
# gitignored build output and local scratch, which is not what ships.
import re
import subprocess

from conftest import REPO_ROOT

# A fabricated trace id in tests/test_phase_2_observability.py, not an account.
ALLOWED_TWELVE_DIGIT = {"000000000000"}

# The document that specifies these checks quotes the patterns, and so does this test.
CREDENTIAL_PATTERN_ALLOWED = {
    "docs/what-is-not-included.md",
    "tests/test_no_account_ids.py",
}

ACCESS_KEY = re.compile(r"AKIA[0-9A-Z]{16}|aws_secret" + r"_access_key")
# A 12-digit run is only an account id when it stands alone. In an ARN it is delimited by
# colons, in an ECR host by a dot. Buried inside a longer token it is a SHA256 digest or a
# base64 blob, which is how provision/.terraform.lock.hcl produced six false positives.
TWELVE_DIGITS = re.compile(r"(?<![0-9A-Za-z])[0-9]{12}(?![0-9A-Za-z])")


def _tracked_text_files():
    """Yield (repo-relative path, text) for every tracked file that is not binary."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
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


def test_no_aws_access_keys_are_tracked():
    offenders = sorted(
        name
        for name, text in _tracked_text_files()
        if name not in CREDENTIAL_PATTERN_ALLOWED and ACCESS_KEY.search(text)
    )
    assert not offenders, f"tracked files matching an AWS credential pattern: {offenders}"


def test_the_only_twelve_digit_number_is_the_fabricated_trace_id():
    found = {}
    for name, text in _tracked_text_files():
        for match in TWELVE_DIGITS.findall(text):
            if match not in ALLOWED_TWELVE_DIGIT:
                found.setdefault(match, set()).add(name)
    report = {
        number: sorted(files)[:3] + (["..."] if len(files) > 3 else [])
        for number, files in sorted(found.items())
    }
    assert not found, (
        f"{len(found)} twelve-digit numbers in tracked files that are not the fabricated trace id. "
        f"An AWS account id is twelve digits, so each of these is an account id until proven "
        f"otherwise: {report}"
    )
