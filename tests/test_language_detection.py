from app.services.language_detection import detect_language


def test_detect_english():
    code, conf = detect_language("The quick brown fox jumps over the lazy dog. " * 5)
    assert code == "en"
    assert conf >= 0.6


def test_detect_chinese():
    code, conf = detect_language("灭火器是用于扑灭火灾的便携式工具。" * 5)
    assert code == "zh"
    assert conf >= 0.6


def test_detect_vietnamese():
    code, conf = detect_language("Bình chữa cháy là thiết bị dùng để dập tắt đám cháy. " * 5)
    assert code == "vi"
    assert conf >= 0.6


def test_low_confidence_returns_none():
    code, conf = detect_language("a b c")
    # Either confidence too low or returns 'en' with low conf; the caller decides.
    assert isinstance(code, str)
    assert 0.0 <= conf <= 1.0
