"""Strict acceptance tests for the time synchronization engine."""

from engine.clock.sync import (
    apply_offset,
    estimate_offset,
    future_guard,
    leap_second_adjust,
    monotonic_ok,
    offset_sample,
    sync_batch,
    validate_config,
)


LEAP_TABLE = {20161231235960: 1}

COMPLETE_CONFIG = {
    "max_offset": 5,
    "leap_table": LEAP_TABLE,
    "monotonic": True,
}

HOSTS = [
    {
        "id": "alpha",
        "samples": [
            {"offset": 100, "delay": 5},
            {"offset": 100, "delay": 6},
            {"offset": 100, "delay": 7},
        ],
    },
    {
        "id": "beta",
        "samples": [
            {"offset": 900, "delay": 5},
            {"offset": 900, "delay": 6},
            {"offset": 900, "delay": 7},
        ],
    },
]


def test_offset_sample_discards_negative_delay():
    assert offset_sample(0, 10, 10, 20) == {"offset": 0, "delay": 20}
    assert offset_sample(1000, 1100, 1050, 900) == {}


def test_estimate_offset_uses_median_of_fastest_half():
    samples = [
        {"offset": 100, "delay": 90},
        {"offset": 300, "delay": 40},
        {"offset": 1000, "delay": 10},
        {"offset": 500, "delay": 20},
        {"offset": 700, "delay": 30},
        {"offset": 900, "delay": 50},
    ]
    assert estimate_offset(samples) == 700


def test_apply_offset_consults_monotonic_on_backward_wall():
    assert apply_offset(1_000_000, -250, 1_000_100) == 1_000_100


def test_leap_second_adjust_does_not_double_count_inserted_second():
    before = leap_second_adjust(20161231235959, LEAP_TABLE)
    at_leap = leap_second_adjust(20161231235960, LEAP_TABLE)
    after = leap_second_adjust(20170101000000, LEAP_TABLE)
    assert at_leap == before + 1
    assert after == at_leap + 1


def test_leap_second_adjust_matches_exact_instant_not_year():
    same_year_before_leap = 20161201000000
    with_table = leap_second_adjust(same_year_before_leap, LEAP_TABLE)
    without_table = leap_second_adjust(same_year_before_leap, {})
    assert with_table == without_table


def test_monotonic_ok_rejects_equal_timestamps():
    assert monotonic_ok(500, 500) is False
    assert monotonic_ok(501, 500) is False


def test_future_guard_rejects_far_future_timestamp():
    now = 1_700_000_000
    assert future_guard(now + 86_400, now, 300) is False


def test_future_guard_includes_window_upper_bound():
    now = 1_700_000_000
    assert future_guard(now + 300, now, 300) is True
    assert future_guard(now + 301, now, 300) is False


def test_validate_config_requires_monotonic_clock():
    config = {
        "max_offset": 5,
        "leap_table": LEAP_TABLE,
        "monotonic": False,
    }
    assert validate_config(config) == ["monotonic_disabled"]


def test_sync_batch_uses_per_host_offset():
    result = sync_batch(HOSTS, COMPLETE_CONFIG)
    assert result == {"alpha": 100, "beta": 900}


def test_estimate_offset_returns_zero_without_samples():
    assert estimate_offset([]) == 0


def test_offset_sample_symmetric_round_trip_gives_pure_offset():
    result = offset_sample(1000, 1060, 1060, 1020)
    assert result == {"offset": 50, "delay": 20}


def test_apply_offset_backward_is_detected_without_wall_mutation():
    wall = 1_000_000
    result = apply_offset(wall, -10, 999_995)
    assert result == wall
    assert result != wall - 10
    assert wall == 1_000_000


def test_leap_second_timestamp_is_not_repeated():
    values = [
        leap_second_adjust(20161231235959, LEAP_TABLE),
        leap_second_adjust(20161231235960, LEAP_TABLE),
        leap_second_adjust(20170101000000, LEAP_TABLE),
    ]
    assert len(set(values)) == 3


def test_sync_batch_independent_batches_match_individual_syncs():
    alpha = sync_batch([HOSTS[0]], COMPLETE_CONFIG)
    beta = sync_batch([HOSTS[1]], COMPLETE_CONFIG)
    combined = sync_batch(HOSTS, COMPLETE_CONFIG)
    assert combined == {**alpha, **beta}