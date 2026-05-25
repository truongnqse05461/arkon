import litellm


def test_langfuse_importable():
    """Package is installed and exposes its primary client class."""
    import langfuse
    assert hasattr(langfuse, "Langfuse"), "Langfuse client class missing from package"


def test_tracing_enabled_when_key_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    litellm.success_callbacks = []
    litellm.failure_callbacks = []

    from app.ai.tracing import configure_langfuse_tracing
    result = configure_langfuse_tracing()

    assert result is True
    assert "langfuse" in litellm.success_callbacks
    assert "langfuse" in litellm.failure_callbacks


def test_tracing_disabled_when_key_absent(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    litellm.success_callbacks = []
    litellm.failure_callbacks = []

    from app.ai.tracing import configure_langfuse_tracing
    result = configure_langfuse_tracing()

    assert result is False
    assert "langfuse" not in litellm.success_callbacks
    assert "langfuse" not in litellm.failure_callbacks
