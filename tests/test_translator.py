import pytest

from app.ai.mrp.translator import (
    TranslationOutput,
    validate_translation,
    InvalidTranslationError,
)


def test_validate_translation_happy_path():
    src = "# Heading\n\nSee [[concept/x]] and 【source/y】 for details."
    tgt = "# Tiêu đề\n\nXem [[concept/x]] và 【source/y】 để biết chi tiết."
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    validate_translation(src_content=src, output=out)  # no exception


def test_validate_translation_rejects_missing_wikilink():
    src = "[[concept/a]] [[concept/b]]"
    tgt = "[[concept/a]] foo"  # second link dropped
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="wikilink count"):
        validate_translation(src_content=src, output=out)


def test_validate_translation_rejects_truncation():
    src = "x" * 1000
    tgt = "y" * 100  # 10% of source — under 50% bound
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="length"):
        validate_translation(src_content=src, output=out)


def test_validate_translation_rejects_runaway_expansion():
    src = "x" * 100
    tgt = "y" * 250  # 250% — over 200% bound
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="length"):
        validate_translation(src_content=src, output=out)
