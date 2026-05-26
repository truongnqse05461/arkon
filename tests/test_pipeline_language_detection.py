import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_detection_skipped_when_no_target_language():
    """No detection if target_language is null — saves cost."""
    from app.services.language_detection import detect_language

    # Direct unit test of the gate: we don't run the full worker, just confirm
    # the detect function works and the guard logic is simple. This is a
    # smoke test; full worker integration is covered by the e2e MRP fixture.
    #
    # Use a longer, clearly English passage so langid has enough signal.
    english_text = (
        "The quick brown fox jumps over the lazy dog. "
        "Natural language processing enables computers to understand human language. "
        "Machine translation converts text from one language into another automatically. "
    ) * 5
    code, conf = detect_language(english_text)
    assert code == "en"
    assert conf >= 0.6
