# Alternative Paths

Reference-level guidance for serving paths the workshop does not demo live. These are documented for take-home use, not tested during the session. Each path gives the config shape and the official docs to follow. Marked clearly as untested here.

The workshop serves a small model on CPU so it runs on standard clusters. The two alternatives below trade that portability for performance or managed infrastructure.

## GPU acceleration

Not tested live. To serve on GPU instead of CPU:

- Use a GPU node group (for example a g5 or g6 instance family on EKS) instead of the t3 worker.
- Swap the vLLM CPU image for the standard CUDA vLLM image and drop the CPU-specific flags (`--device cpu`, `VLLM_CPU_*`).
- Larger models become practical. The KServe InferenceService and the kagent ModelConfig wiring are unchanged.
- Follow the vLLM and KServe GPU serving docs for the current image tags and resource requests.

## Amazon Bedrock

Not tested live. To route inference to Amazon Bedrock instead of in-cluster vLLM:

- Set the kagent ModelConfig `provider: Bedrock` with a `bedrock.region` and a Bedrock model id (see `research-findings-june-2026.md` section 7 for the YAML).
- Authenticate with EKS Pod Identity, no static key. Scope the IAM role to `bedrock:InvokeModel` on specific model ids only.
- AWS Budgets is a soft alert with an 8 to 24 hour data lag, not a real-time hard cap. The IAM model-id allowlist is the actual spend guardrail.
- Follow the AWS Bedrock and EKS Pod Identity docs for current model ids and role setup.

To upgrade either path from reference-level to a tested walkthrough, say so and it gets validated against real infrastructure.
