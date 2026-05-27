"""Test that source upload entry points accept and persist `target_language`.

The file upload uses raw `Form(...)` parameters, so we verify the FastAPI
endpoint signature includes the field. The URL upload uses a Pydantic schema
(SourceCreateURL), so we exercise that directly.
"""

import inspect

from app.routers.sources import SourceCreateURL, upload_source


def test_url_create_accepts_target_language():
    m = SourceCreateURL(url="https://example.com", target_language="vi")
    assert m.target_language == "vi"


def test_url_create_target_language_optional():
    m = SourceCreateURL(url="https://example.com")
    assert m.target_language is None


def test_upload_endpoint_signature_includes_target_language():
    """File upload uses Form(...) params, so we confirm the parameter exists."""
    sig = inspect.signature(upload_source)
    assert "target_language" in sig.parameters
    param = sig.parameters["target_language"]
    # Default value should be a Form(...) marker with default None.
    assert param.default is not inspect.Parameter.empty
