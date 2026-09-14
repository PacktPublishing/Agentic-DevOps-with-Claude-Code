# ABOUTME: Unit tests for the shared phase-gate helpers in conftest, which need no cluster.
# ABOUTME: A helper that mangles output turns a working endpoint into a failing test.
import json

import pytest

from conftest import _clean_curl_output


# kubectl's pod-deletion notice lands on stdout with no separator, so a JSON body came back as
# `{...}\n200pod "x" deleted from ns namespace` and json.loads raised `Extra data: line 2 column 1`.
# That reads as a broken model endpoint. It was a broken parser, and the endpoint was fine.
@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a": 1}\n200pod "phasetest-curl-1" deleted from kserve namespace\n', '{"a": 1}\n200'),
        ('{"a": 1}\n200pod "phasetest-curl-1" deleted\n', '{"a": 1}\n200'),
        ('{"a": 1}\n200\n', '{"a": 1}\n200'),
        ('{"a": 1}\n200', '{"a": 1}\n200'),
    ],
)
def test_kubectl_deletion_notice_is_stripped(raw, expected):
    assert _clean_curl_output(raw) == expected


def test_stripping_leaves_a_body_that_parses():
    """The point of the strip: what comes back must survive the caller's json.loads."""
    raw = '{"model": "qwen3-1.7b"}\n200pod "phasetest-curl-9" deleted from kserve namespace\n'
    cleaned = _clean_curl_output(raw)
    assert json.loads(cleaned.rsplit("\n", 1)[0])["model"] == "qwen3-1.7b"


def test_a_body_mentioning_a_deleted_pod_is_not_eaten():
    """Only a trailing notice is stripped; the same words inside a payload must survive.

    An over-greedy pattern here would silently truncate a real response that happens to talk about
    a deleted pod, which is exactly the kind of log or event body these tests query for.
    """
    raw = '{"msg": "pod \\"api-7\\" deleted from prod namespace"}\n200'
    assert _clean_curl_output(raw) == raw
