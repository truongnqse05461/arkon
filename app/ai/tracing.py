import os
import types

import litellm

# Compat: langfuse 4.x removed `langfuse.version` submodule; litellm references
# `langfuse.version.__version__`. Create a stub module so litellm can read it.
try:
    import langfuse as _langfuse
    if not hasattr(_langfuse, "version") or isinstance(_langfuse.version, str):
        _v = types.ModuleType("langfuse.version")
        _v.__version__ = _langfuse.__version__
        _langfuse.version = _v
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
