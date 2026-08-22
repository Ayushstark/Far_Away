from backend.app.services.speech import sanitize_tts_text


def test_sanitize_tts_text_strips_exclamation_marks_english() -> None:
    cleaned = sanitize_tts_text("Great job staying hydrated today!")

    assert "!" not in cleaned
    assert "exclamation" not in cleaned.lower()


def test_sanitize_tts_text_strips_exclamation_marks_hindi() -> None:
    cleaned = sanitize_tts_text("बहुत बढ़िया! आपने आज दवा समय पर ली!")

    assert "!" not in cleaned


def test_sanitize_tts_text_strips_asterisks_and_markdown_emphasis() -> None:
    cleaned = sanitize_tts_text("**Take your medicine** and *rest well*!")

    assert "*" not in cleaned
    assert "!" not in cleaned
