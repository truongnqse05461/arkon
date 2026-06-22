"""Re-translate endpoint: request model + handler signature.

Mirrors test_sources_target_language.py — the codebase tests routers at the
model/signature level rather than via a live HTTP client.
"""

import inspect

from app.routers.sources import RetranslateRequest, retranslate_source


def test_request_defaults_to_none():
    m = RetranslateRequest()
    assert m.target_language is None
    assert m.source_language is None


def test_request_accepts_languages():
    m = RetranslateRequest(target_language="vi", source_language="zh")
    assert m.target_language == "vi"
    assert m.source_language == "zh"


def test_endpoint_signature():
    sig = inspect.signature(retranslate_source)
    assert "source_id" in sig.parameters
    assert "body" in sig.parameters
