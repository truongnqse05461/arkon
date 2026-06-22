from app.config import settings


def test_translation_enabled_default_true():
    assert settings.translation_enabled is True


def test_translation_model_spec_id_default_none():
    assert settings.translation_model_spec_id is None


def test_language_detection_min_confidence_default():
    assert settings.language_detection_min_confidence == 0.6
