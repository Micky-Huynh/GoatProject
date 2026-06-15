from __future__ import annotations

from goat_data.playoffs import _max_consecutive_seasons, _repeat_titles_score


def test_max_consecutive_seasons() -> None:
    assert _max_consecutive_seasons([]) == 0
    assert _max_consecutive_seasons([1991]) == 1
    assert _max_consecutive_seasons([1991, 1992, 1993, 1996, 1997, 1998]) == 3


def test_repeat_titles_score_rewards_dynasty_runs() -> None:
    cfg = {
        "consecutive_bonus_per_ring": 0.75,
        "dynasty_threshold": 3,
        "dynasty_bonus": 1.5,
    }
    jordan_max, jordan_score = _repeat_titles_score([1991, 1992, 1993, 1996, 1997, 1998], cfg)
    jokic_max, jokic_score = _repeat_titles_score([2023], cfg)

    assert jordan_max == 3
    assert jordan_score > jokic_score
    assert jokic_max == 1
    assert jokic_score == 1.0
