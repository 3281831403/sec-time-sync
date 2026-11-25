"""Time synchronization primitives.

The eight public functions implement the contracts in their docstrings;
the acceptance tests in tests/clock/test_sync.py must not be weakened.
"""

from datetime import date


def _decode_timestamp(ts):
    """Split a YYYYMMDDHHMMSS integer into calendar/clock components."""
    text = str(int(ts))
    return (
        int(text[0:4]),
        int(text[4:6]),
        int(text[6:8]),
        int(text[8:10]),
        int(text[10:12]),
        int(text[12:14]),
    )


def offset_sample(t1, t2, t3, t4) -> dict:
    """Compute one round-trip sample.

    The sample contains the NTP offset and delay as integer keys named offset
    and delay. A negative delay is physically impossible and must be discarded
    by returning an empty dictionary. A zero delay is valid.
    """
    offset = ((t2 - t1) + (t3 - t4)) // 2
    delay = (t4 - t1) - (t3 - t2)
    if delay < 0:
        return {}
    return {"offset": offset, "delay": delay}


def estimate_offset(samples) -> int:
    """Estimate an offset from multiple samples.

    Sort samples by their delay, keep the fastest half, and return the median
    of the offsets in that half. For an even-sized half, average the two middle
    values with integer division. With no samples the estimate is zero.
    """
    if not samples:
        return 0

    fastest_count = max(1, len(samples) // 2)
    fastest_half = sorted(samples, key=lambda sample: sample["delay"])[:fastest_count]
    offsets = sorted(sample["offset"] for sample in fastest_half)

    middle = len(offsets) // 2
    if len(offsets) % 2 == 1:
        return offsets[middle]
    return (offsets[middle - 1] + offsets[middle]) // 2


def apply_offset(wall, offset, monotonic) -> int:
    """Apply an offset without ever moving the wall clock backwards.

    Compute wall plus offset. If that result is earlier than wall, a backwards
    correction has been detected: return the larger of wall and the trusted
    monotonic reading, never the earlier candidate. Valid forward corrections
    return wall plus offset. Neither input is mutated.
    """
    candidate = wall + offset
    if candidate < wall:
        return max(wall, monotonic)
    return candidate


def leap_second_adjust(ts, leap_table) -> int:
    """Map an encoded UTC timestamp onto a continuous logical timeline.

    ts is an integer encoded as YYYYMMDDHHMMSS. leap_table is keyed by the
    exact encoded instant of each inserted leap second and stores the
    cumulative insertion count at that instant. Only an exact instant matches,
    never a whole year. The inserted second occupies exactly one logical second
    between the preceding and following timestamps, so it is neither repeated
    nor skipped.
    """
    year, month, day, hour, minute, second = _decode_timestamp(ts)
    logical = date(year, month, day).toordinal() * 86400
    logical += hour * 3600 + minute * 60 + second

    if ts in leap_table:
        # The encoded :60 label already occupies the inserted second in this
        # ordinal scale, so only earlier cumulative insertions are added.
        logical += leap_table[ts] - 1
    else:
        # Match only the exact encoded instant: use the cumulative count of
        # the latest leap instant strictly before ts. Year-only keys never
        # match here.
        prior_keys = [leap_ts for leap_ts in leap_table if leap_ts < ts]
        if prior_keys:
            logical += leap_table[max(prior_keys)]

    return logical


def monotonic_ok(prev, cur) -> bool:
    """Return true only when the monotonic reading strictly advances.

    Equal readings are not acceptable because they can represent a repeated
    timestamp. Any backwards movement is rejected immediately.
    """
    return prev < cur


def future_guard(ts, now, window) -> bool:
    """Accept timestamps inside a finite inclusive window.

    The window is the closed interval from now minus window through now plus
    window. Both endpoints are valid. Values farther in the future than the
    upper endpoint are rejected; the window must not be treated as infinite.
    """
    return (now - window) <= ts <= (now + window)


def validate_config(config) -> list[str]:
    """Return a list of configuration problem codes.

    Report max_offset_missing when no positive maximum offset is configured,
    leap_table_missing when the leap table is absent or empty, and
    monotonic_disabled when monotonic clock use is not enabled. A complete
    configuration returns an empty list.
    """
    problems = []

    max_offset = config.get("max_offset")
    if not isinstance(max_offset, (int, float)) or max_offset <= 0:
        problems.append("max_offset_missing")

    if not config.get("leap_table"):
        problems.append("leap_table_missing")

    if not config.get("monotonic"):
        problems.append("monotonic_disabled")

    return problems


def sync_batch(hosts, config) -> dict:
    """Synchronize a batch of hosts independently.

    hosts is a sequence of mappings with an id and a samples list. The result
    maps each host id to that host's own estimated offset. Offsets must never be
    reused across hosts, and separate calls must not share mutable state.
    """
    return {
        host["id"]: estimate_offset(list(host.get("samples", [])))
        for host in hosts
    }