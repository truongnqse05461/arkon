import os

import litellm


def configure_langfuse_tracing() -> bool:
    """Register Langfuse LiteLLM callbacks if LANGFUSE_PUBLIC_KEY is set. Returns True if enabled."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return False
    litellm.success_callbacks = ["langfuse"]
    litellm.failure_callbacks = ["langfuse"]
    return True
