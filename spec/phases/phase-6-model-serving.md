# Phase 6: Model serving (chapter 8)

**Goal:** KServe serving the small in-cluster model via vLLM on CPU, one inference answered, the agent trace landed in Tempo, and llm-d shown as the scheduling-layer topology.

**Inputs:** Phase 5 complete (kagent, agentgateway). cert-manager (for KServe webhooks). The vLLM CPU image pre-pulled.

**Outputs:**
- KServe (v0.19.0) installed in RawDeployment mode from its OCI charts (kserve-crd then resources), cert-manager present
- An InferenceService (`serving.kserve.io/v1beta1`) serving Qwen3-1.7B (backup Qwen3-0.6B) via the vLLM CPU image `vllm/vllm-openai-cpu:v0.23.0-x86_64`, exposing an OpenAI-compatible endpoint
- The kagent demo agent's ModelConfig from Phase 5 resolves against this endpoint; one inference request answered
- The agent call's OTel trace walked in Tempo with `gen_ai.*` attributes; the AI-plane Grafana dashboard loads
- llm-d (v0.7.0) shown as the distributed-inference scheduling topology, included as an architecture reference, with honest CNCF Sandbox framing rather than a running install

**Test criteria (tests/test_phase_6_model_serving.py):**
- The InferenceService is Ready and answers `/v1/chat/completions`
- The model name matches vLLM's `--served-model-name`
- A trace for the inference appears in Tempo with `gen_ai.request.model` and token-count attributes
- The pod has the `SYS_NICE` capability and `VLLM_CPU_KVCACHE_SPACE` set

**Completion promise:** `<promise>PHASE6_DONE</promise>`

**Key decisions:**
- vLLM CPU: `--device cpu --dtype bfloat16`, `VLLM_CPU_KVCACHE_SPACE` 2 to 4 on the t3.2xlarge, `SYS_NICE`, `--max-model-len` well below 32768. Pre-warm the model; the pre-warmed-request fallback exists if the latency gate is missed.
- KServe RawDeployment, not Knative (Knative mode is phasing out). InferenceService is `v1beta1`; treat LLMInferenceService (v1alpha1, built on llm-d) as preview.
- vLLM is PyTorch Foundation, not CNCF. llm-d is CNCF Sandbox, pre-1.0; do not call it production-ready.

**Stop here.** Output the completion promise and wait. Run one inference and follow its trace end to end; the span carries the model name and the token counts.
