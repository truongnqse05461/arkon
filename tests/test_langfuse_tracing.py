def test_langfuse_importable():
    """Package is installed and exposes its primary client class."""
    import langfuse
    assert hasattr(langfuse, "Langfuse"), "Langfuse client class missing from package"
