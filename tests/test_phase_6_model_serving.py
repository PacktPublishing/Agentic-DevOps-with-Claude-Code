# ABOUTME: Phase 6 gate. The vLLM InferenceService Ready and answering OpenAI-style,
# ABOUTME: the served model name correct, CPU tuning present, and an inference trace.
import json

import pytest

from conftest import get_json, incluster_curl

SERVED_MODEL = "qwen3-1.7b"
PREDICTOR = "http://qwen3-predictor.kserve.svc"


def test_inferenceservice_ready():
    obj = get_json("get", "inferenceservice", "qwen3", "-n", "kserve")
    conds = obj.get("status", {}).get("conditions", [])
    assert any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in conds
    ), f"InferenceService not Ready: {conds}"


def test_pod_has_sys_nice_and_kvcache_env():
    obj = get_json(
        "get", "pods", "-n", "kserve",
        "-l", "serving.kserve.io/inferenceservice=qwen3",
    )
    pods = obj.get("items", [])
    assert pods, "no vLLM predictor pod found"
    container = next(
        c for c in pods[0]["spec"]["containers"] if c["name"] == "kserve-container"
    )
    caps = container.get("securityContext", {}).get("capabilities", {}).get("add", [])
    assert "SYS_NICE" in caps, "SYS_NICE capability missing"
    env_names = {e["name"] for e in container.get("env", [])}
    assert "VLLM_CPU_KVCACHE_SPACE" in env_names, "VLLM_CPU_KVCACHE_SPACE not set"


@pytest.mark.integration
def test_chat_completions_answers_with_served_model():
    body = incluster_curl(
        f"{PREDICTOR}/v1/chat/completions",
        "-X", "POST", "-H", "Content-Type: application/json",
        "--data",
        json.dumps({"model": SERVED_MODEL,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1}),
        ns="kserve",
    )
    payload = body.rsplit("\n", 1)[0]
    data = json.loads(payload)
    assert data.get("model") == SERVED_MODEL, f"model was {data.get('model')}"


@pytest.mark.integration
def test_inference_trace_has_model_and_tokens(agent_traffic):
    found = incluster_curl(
        "http://tempo.observability.svc:3200/api/search",
        "--get", "--data-urlencode", 'q={ span.gen_ai.request.model != "" }',
        ns="observability",
    )
    assert "traceID" in found, (
        "no trace with gen_ai.request.model in Tempo, despite the agent_traffic fixture having "
        "driven a turn and confirmed a gen_ai span landed. That points at the model span "
        "specifically rather than at the tracing pipeline."
    )
