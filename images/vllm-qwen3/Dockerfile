# ABOUTME: vLLM CPU image with Qwen3-1.7B weights baked in, so pods load from disk and
# ABOUTME: never hit HuggingFace at runtime, which otherwise costs a ~14-minute download per pod.
FROM vllm/vllm-openai-cpu:v0.23.0-x86_64

ARG MODEL=Qwen/Qwen3-1.7B

# Download the weights into the image during build (online), then force offline at runtime
# so vLLM uses the baked snapshot and never contacts the Hub.
USER root
ENV HF_HOME=/models
RUN python3 -c "from huggingface_hub import snapshot_download; snapshot_download('${MODEL}')" \
    && chmod -R a+rX /models
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
