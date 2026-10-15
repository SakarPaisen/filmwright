import pytest

from filmwright.core.voice.qwen import MIN_SCORE, match_score, speech_seconds, words


@pytest.mark.parametrize("expected, heard", [
    ("今日は良い天気です。", "ラーメンが食べたい。"),          # Japanese
    ("这个按钮会分享任务。", "我们明天见。"),                  # Chinese
    ("안녕하세요", "감사합니다"),                              # Korean
    ("Привет, мир", "Пока"),                                  # Russian
])
def test_unrelated_lines_in_other_scripts_fail(expected, heard):
    assert match_score(expected, heard) < MIN_SCORE


@pytest.mark.parametrize("expected, heard", [
    ("今日は良い天気です。", "今日は良い天気です"),
    ("Café crème brûlée.", "Cafe creme brulee"),               # Whisper may drop accents
    ("Grüße aus München!", "Grüsse aus Munchen"),
    ("Acme Tasks is ready.", "acme tasks is ready"),
    ("ＡＣＭＥ　Ｔａｓｋｓ", "ACME Tasks"),                       # full-width forms
])
def test_matching_lines_pass(expected, heard):
    assert match_score(expected, heard) >= MIN_SCORE


def test_nothing_to_compare_is_never_a_free_pass():
    assert match_score("...", "...") == 0.0
    assert match_score("Hello there.", "") == 0.0


def test_words_keep_every_script():
    assert words("今日は") == ["今日は"]
    assert words("Don't stop, it's 3!") == ["don't", "stop", "it's", "3"]


def test_spoken_length_counts_characters_where_there_are_no_spaces():
    jp = "このボタンを押すと、すべてのタスクがチームの全員に共有されます。"
    assert speech_seconds(jp) > 4.0                       # was 1.0 s, so every real take looked "runaway"
    assert 3.0 < speech_seconds("Pick a mood, choose your outputs, and filmwright builds the whole film.") < 6.0
