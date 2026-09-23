# ABOUTME: Cluster-free tests for the probe scripts' pure logic: percentile ranking, audit-line
# ABOUTME: summarisation, trace attribute extraction, and time-window parsing.
#
# The probes themselves need a cluster, so the parts that can be wrong without one are tested here.
# Every function covered has a failure mode that is silent in production: a percentile off by one
# reports a latency nobody measured, and an audit summary that counts unattributable lines as
# attributed makes an ungoverned trail look governed.
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The probe scripts import requests at module scope. Without this, a reader who has not installed
# it gets a collection error, and a collection error aborts the whole run: `pytest` at the repo
# root then reports zero tests rather than skipping these few. Install it with
# `pip install -r scripts/requirements-trace.txt`.
pytest.importorskip("requests")

from benchmark_inference import _percentile
from trace_probe import attrs_in_trace
from verify_audit_event import _since_seconds, summarise


# --- percentile ---------------------------------------------------------------------------------

@pytest.mark.parametrize("pct,expected", [(10, 1), (50, 5), (90, 9), (100, 10)])
def test_percentile_is_nearest_rank(pct, expected):
    # Nearest rank returns a value that was actually measured. Interpolation would return 9.1 for
    # p90 here, which no request ever took.
    assert _percentile(list(range(1, 11)), pct) == expected


def test_percentile_edge_cases():
    import math
    assert math.isnan(_percentile([], 50))
    assert _percentile([4.2], 90) == 4.2
    assert _percentile([1.0, 9.0], 90) == 9.0


# --- audit summarisation ------------------------------------------------------------------------

def test_summarise_counts_and_attributes():
    streams = [{
        "stream": {"job": "claude-audit"},
        "values": [
            ["1", '{"tool_name": "Bash", "agent_identity": "agent-a"}'],
            ["2", '{"tool_name": "Read", "agent_identity": "agent-a"}'],
            ["3", '{"tool_name": "Bash", "agent_identity": "agent-b"}'],
        ],
    }]
    total, attributed, tools, identities = summarise(streams)
    assert (total, attributed) == (3, 3)
    assert tools == {"Bash": 2, "Read": 1}
    assert identities == {"agent-a", "agent-b"}


def test_summarise_flags_unattributable_lines():
    # The case that matters: lines exist, a dashboard renders them, but nothing says who acted.
    streams = [{"stream": {"job": "claude-audit"}, "values": [
        ["1", '{"tool_name": "Bash", "agent_identity": "agent-a"}'],
        ["2", '{"tool_name": "Bash"}'],
    ]}]
    total, attributed, _tools, _ids = summarise(streams)
    assert total == 2 and attributed == 1, "an identity-less line must not count as attributed"


def test_summarise_takes_identity_from_stream_label():
    # Identity may live on the stream label rather than in the line body; both are attributable.
    streams = [{"stream": {"agent_identity": "agent-c"}, "values": [["1", '{"tool_name": "Grep"}']]}]
    total, attributed, tools, identities = summarise(streams)
    assert (total, attributed, identities) == (1, 1, {"agent-c"})
    assert tools == {"Grep": 1}


def test_summarise_survives_non_json_lines():
    # A malformed line is still an audit line; it must be counted, not crash the probe.
    streams = [{"stream": {}, "values": [["1", "not json at all"]]}]
    total, attributed, tools, _ids = summarise(streams)
    assert (total, attributed, tools) == (1, 0, {})


# --- window parsing -----------------------------------------------------------------------------

@pytest.mark.parametrize("since,seconds", [("30s", 30), ("5m", 300), ("2h", 7200), ("7d", 604800)])
def test_since_seconds(since, seconds):
    assert _since_seconds(since) == seconds


@pytest.mark.parametrize("bad", ["", "h", "10", "10x", "-5m", "abc"])
def test_since_rejects_garbage(bad):
    with pytest.raises(ValueError):
        _since_seconds(bad)


# --- trace attributes ---------------------------------------------------------------------------

def test_attrs_in_trace_walks_every_span():
    trace = {"batches": [
        {"scopeSpans": [{"spans": [
            {"attributes": [{"key": "gen_ai.request.model"}, {"key": "gen_ai.system"}]},
            {"attributes": [{"key": "gen_ai.usage.input_tokens"}]},
        ]}]},
        {"scopeSpans": [{"spans": [{"attributes": [{"key": "http.method"}]}]}]},
    ]}
    assert attrs_in_trace(trace) == {
        "gen_ai.request.model", "gen_ai.system", "gen_ai.usage.input_tokens", "http.method",
    }


def test_attrs_in_trace_handles_empty_and_malformed():
    assert attrs_in_trace({}) == set()
    assert attrs_in_trace({"batches": [{"scopeSpans": [{"spans": [{}]}]}]}) == set()
    assert attrs_in_trace({"batches": [{"scopeSpans": [{"spans": [
        {"attributes": [{"key": ""}, {"novalue": 1}]}]}]}]}) == set()
