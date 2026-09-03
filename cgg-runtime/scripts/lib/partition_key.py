#!/usr/bin/env python3
"""partition_key.py — the ONE declared clock for daily-file partition keys.

THE LAW (bk-daily-partition-key-shared-clock-primitive, admitted /review 767 Q4,
B2 wave 5; the clock itself RULED /review 745 Q2):

    A daily-file partition key is a cross-lane JOIN key. Derive it from ONE
    declared clock — UTC — through this shared helper. NEVER per-writer.

WHY (the failure this primitive answers, lived not hypothesized):
    At tic 745 a SINGLE tic emission, emission_id em-745-0571cb8829, instant
    2026-08-28T01:05:32Z, produced TWO differently-dated daily files:

        audit-logs/tics/2026-08-28.jsonl              (UTC clock — correct)
        audit-logs/mogul/mandates/history/2026-08-27.jsonl  (LOCAL clock)

    The mandate row inside the 08-27 file carries created_at
    "2026-08-28T01:05:32.916283+00:00" — the row's own content disagrees with
    the name of the file holding it. Any consumer joining tics/<date> against
    mandates/history/<date> silently loses that boundary. A per-writer clock
    does not produce a wrong timestamp; it produces a broken JOIN.

SCOPE OF THE DIVERGENCE (measured, A3-749 forward; control held at the t750
boot, 05:27Z = 01:27 EDT, one date): for a UTC-negative local zone the local
date trails the UTC date only between local 20:00 and 24:00 (EDT, UTC-4).
Outside that window a local-clock writer is accidentally correct — which is
exactly why the defect survives: it is right ~83% of the day.

USAGE (python writers):
    from lib.partition_key import utc_partition_date
    partition = utc_partition_date()          # 'YYYY-MM-DD', UTC, always
    daily_file = history_dir / f"{partition}.jsonl"

USAGE (shell writers — the SAME law, expressed in the shell's own idiom; keep
these in lockstep with this module):
    TODAY=$(date -u +%Y-%m-%d)                # daily partition key
    TIMESTAMP=$(date -u +%Y-%m-%dT%H%M%S)     # artifact-naming timestamp

NAIVE DATETIMES ARE REFUSED. A datetime carrying no tzinfo has no declared
clock, which is precisely the ambiguity this primitive exists to remove; the
helper raises rather than guessing UTC or local. Guessing is how the t745
divergence entered the substrate in the first place.

FORWARD-ONLY. Historical dated files are NEVER renamed — the pre-cure names
are the audit record of the defect, not debt to be scrubbed.
"""

from datetime import datetime, timezone

__all__ = ["utc_partition_date", "PARTITION_DATE_FORMAT", "PARTITION_CLOCK"]

# The declared clock. Named as data, not buried in a call, so a reader (and a
# guard) can cite WHICH clock the federation ruled without reading the body.
PARTITION_CLOCK = "UTC"

# The declared key shape. Every daily-file lane in the federation is
# <YYYY-MM-DD>.jsonl; the format lives here so the shape and the clock are
# read from ONE place.
PARTITION_DATE_FORMAT = "%Y-%m-%d"


def utc_partition_date(now: datetime = None) -> str:
    """Return the daily-file partition key 'YYYY-MM-DD' on the ruled UTC clock.

    Args:
        now: OPTIONAL aware datetime to derive the key from. Any timezone is
            accepted and CONVERTED to UTC (an aware datetime denotes a single
            instant regardless of the offset it is written in). Omit it — or
            pass None — to read the current instant from the UTC clock.

    Returns:
        The UTC calendar date as 'YYYY-MM-DD'.

    Raises:
        TypeError: `now` is not a datetime.
        ValueError: `now` is NAIVE (tzinfo is None, or its utcoffset is None).
            A naive datetime carries no declared clock; refusing it is the
            whole point of the primitive.

    The optional `now` is what makes this testable WITHOUT the wall clock: the
    committed suite injects fixed instants across the divergence window rather
    than waiting for 20:00 EDT to come around.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif not isinstance(now, datetime):
        raise TypeError(
            f"utc_partition_date() expects a datetime or None, got "
            f"{type(now).__name__}"
        )
    elif now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError(
            "utc_partition_date() refuses a NAIVE datetime: it carries no "
            "declared clock, and guessing one (UTC? local?) is the exact "
            "ambiguity this primitive exists to remove. Pass an aware "
            "datetime (datetime.now(timezone.utc), or any aware instant) or "
            "pass None to read the ruled UTC clock directly."
        )
    return now.astimezone(timezone.utc).strftime(PARTITION_DATE_FORMAT)
