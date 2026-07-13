import os

import litellm

# Monkey-patch: litellm expects langfuse.version but langfuse>=4 uses __version__
try:
    import langfuse
    if not hasattr(langfuse, "version") and hasattr(langfuse, "__version__"):
        langfuse.version = langfuse.__version__
except ImportError:
    pass


def configure_langfuse_tracing() -> bool:
    """Register Langfuse LiteLLM callbacks if LANGFUSE_PUBLIC_KEY is set. Returns True if enabled."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return False
    if "langfuse" not in litellm.success_callback:
        litellm.success_callback.append("langfuse")
    if "langfuse" not in litellm.failure_callback:
        litellm.failure_callback.append("langfuse")
    return True
