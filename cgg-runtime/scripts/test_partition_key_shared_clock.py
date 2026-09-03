#!/usr/bin/env python3
"""Committed suite for lib/partition_key.py — the shared UTC partition-key clock.

Row bk-daily-partition-key-shared-clock-primitive, B2 wave 5, admitted
/review 767 Q4. The row's stop condition demands: "a committed test proves the
20:00-24:00 EDT divergence window yields ONE date under the helper + NC: a
local-clock writer control shows the divergence the cure removes."

Both halves are here, and the CONTROL is the load-bearing one: an assertion
that the helper returns one date proves nothing unless the same instants are
shown to produce TWO dates under the pre-cure local-clock derivation. Arm 2 is
that discriminator — it fails loudly if the divergence it models ever stops
being real, so this suite cannot silently degrade into a tautology.

EVERY instant is INJECTED. Nothing here reads the wall clock, so the suite
behaves identically at 03:00 UTC and at 23:00 UTC, in EDT and in UTC, in CI and
on the primary machine. A clock test that depends on the clock is not a test.

Fixture zone: EDT = UTC-4 as a FIXED offset (timezone(timedelta(hours=-4))),
not a zoneinfo lookup — the suite must not depend on the tzdata database being
installed, and the divergence being modeled is a function of the OFFSET, not of
any particular political timezone's DST history.
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# --- Load the module under test by absolute path -----------------------------
# Mirrors the sibling-test convention in this directory (scripts/ is not an
# importable package and pytest runs with --import-mode=importlib).
_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib",
                    "partition_key.py")
_spec = importlib.util.spec_from_file_location("partition_key", _LIB)
partition_key = importlib.util.module_from_spec(_spec)
sys.modules["partition_key"] = partition_key
_spec.loader.exec_module(partition_key)

utc_partition_date = partition_key.utc_partition_date

# EDT — the local zone of the primary machine, as a fixed offset.
EDT = timezone(timedelta(hours=-4))


def local_clock_partition_date(instant: datetime) -> str:
    """The PRE-CURE derivation, modeled exactly.

    This is what `datetime.now().strftime("%Y-%m-%d")` (mandate-write.py:416)
    and `date +%Y-%m-%d` (mogul-runner.sh:317, session-restore.sh:831) compute:
    the calendar date of the instant as seen from the machine's LOCAL zone.
    Modeled as an explicit EDT conversion so the control is deterministic
    instead of inheriting the test host's TZ.
    """
    return instant.astimezone(EDT).strftime("%Y-%m-%d")


# The divergence window: local 20:00-24:00 EDT == UTC 00:00-04:00 the NEXT day.
# Each entry is (utc_instant, expected_utc_date, expected_local_date).
DIVERGENCE_WINDOW = [
    # exact window open — 20:00:00 EDT
    (datetime(2026, 8, 28, 0, 0, 0, tzinfo=timezone.utc), "2026-08-28", "2026-08-27"),
    # THE t745 LIVED INSTANT — emission em-745-0571cb8829. On disk this produced
    # tics/2026-08-28.jsonl AND mandates/history/2026-08-27.jsonl.
    (datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc), "2026-08-28", "2026-08-27"),
    # mid-window
    (datetime(2026, 8, 28, 2, 30, 0, tzinfo=timezone.utc), "2026-08-28", "2026-08-27"),
    # last second of the window — 23:59:59 EDT
    (datetime(2026, 8, 28, 3, 59, 59, tzinfo=timezone.utc), "2026-08-28", "2026-08-27"),
    # month boundary — the local clock trails into the PREVIOUS MONTH
    (datetime(2026, 9, 1, 1, 0, 0, tzinfo=timezone.utc), "2026-09-01", "2026-08-31"),
    # year boundary — the local clock trails into the PREVIOUS YEAR
    (datetime(2027, 1, 1, 0, 30, 0, tzinfo=timezone.utc), "2027-01-01", "2026-12-31"),
]

# Outside the window the two clocks agree — the control that keeps the finding
# honestly scoped (A3-749: the divergence is CONFINED to 20:00-24:00 EDT; the
# t750 boot at 05:27Z = 01:27 EDT held one date).
OUTSIDE_WINDOW = [
    # THE t750 LIVED INSTANT — 05:27Z = 01:27 EDT, same date, control held.
    (datetime(2026, 8, 30, 5, 27, 0, tzinfo=timezone.utc), "2026-08-30"),
    # window has not opened yet — 19:59:59 EDT
    (datetime(2026, 8, 28, 23, 59, 59, tzinfo=timezone.utc), "2026-08-28"),
    # midday UTC
    (datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc), "2026-08-28"),
]


# --- ARM 1: THE CURE — one instant, one date, every writer -------------------

@pytest.mark.parametrize("instant,expected_utc,expected_local", DIVERGENCE_WINDOW)
def test_divergence_window_yields_one_date(instant, expected_utc, expected_local):
    """Inside the divergence window the helper yields exactly ONE date.

    Two writers (the tics lane and the mandates/history lane) derive their
    partition from the SAME instant through the SAME helper — the cross-lane
    JOIN key holds.
    """
    tics_lane_partition = utc_partition_date(instant)
    mandate_history_partition = utc_partition_date(instant)

    assert tics_lane_partition == mandate_history_partition, (
        "two writers derived DIFFERENT partitions from one instant — the "
        "shared clock is not shared"
    )
    assert tics_lane_partition == expected_utc
    assert len({tics_lane_partition, mandate_history_partition}) == 1


def test_divergence_window_join_key_holds_across_all_instants():
    """The whole window collapses to one date per instant — no straggler."""
    for instant, expected_utc, _ in DIVERGENCE_WINDOW:
        assert utc_partition_date(instant) == expected_utc, (
            f"{instant.isoformat()} did not partition to {expected_utc}"
        )


# --- ARM 2: THE CONTROL — the divergence the cure removes --------------------
# LOAD-BEARING. If this arm ever passes vacuously the suite has stopped
# discriminating and arm 1 proves nothing.

@pytest.mark.parametrize("instant,expected_utc,expected_local", DIVERGENCE_WINDOW)
def test_local_clock_control_shows_the_divergence(instant, expected_utc, expected_local):
    """The PRE-CURE local-clock derivation yields a DIFFERENT date — the defect.

    This is the negative control: it demonstrates that the instants in
    DIVERGENCE_WINDOW genuinely diverge, so arm 1's agreement is a property of
    the cure and not of a window that never diverged.
    """
    local_date = local_clock_partition_date(instant)
    utc_date = utc_partition_date(instant)

    assert local_date == expected_local
    assert local_date != utc_date, (
        f"CONTROL FAILED TO DISCRIMINATE: {instant.isoformat()} produced the "
        f"same date ({utc_date}) on both clocks. This instant is not in the "
        "divergence window and must not be asserted as one."
    )
    # Two writers, two clocks, ONE instant -> TWO files. Exactly the t745 shape.
    assert len({local_date, utc_date}) == 2


def test_t745_lived_divergence_is_reproduced_exactly():
    """Replays the observed t745 artifact pair, byte-for-byte on the dates.

    On disk: emission em-745-0571cb8829 at 2026-08-28T01:05:32Z wrote
      audit-logs/tics/2026-08-28.jsonl                    (UTC)
      audit-logs/mogul/mandates/history/2026-08-27.jsonl  (LOCAL)
    """
    t745 = datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc)
    assert utc_partition_date(t745) == "2026-08-28"        # the tics lane name
    assert local_clock_partition_date(t745) == "2026-08-27"  # the history name
    # Under the cure BOTH lanes would have named 2026-08-28.
    assert utc_partition_date(t745) != local_clock_partition_date(t745)


# --- ARM 3: SCOPE HONESTY — outside the window there is no divergence --------

@pytest.mark.parametrize("instant,expected_utc", OUTSIDE_WINDOW)
def test_outside_window_both_clocks_agree(instant, expected_utc):
    """Outside 20:00-24:00 EDT the local clock is accidentally correct.

    Keeps the finding honestly scoped and explains why the defect survived:
    a local-clock writer is right for ~83% of the day.
    """
    assert utc_partition_date(instant) == expected_utc
    assert local_clock_partition_date(instant) == expected_utc


# --- ARM 4: THE CLOCK IS DECLARED, NOT GUESSED -------------------------------

def test_naive_datetime_is_refused():
    """A datetime with no tzinfo has no declared clock — the helper refuses."""
    naive = datetime(2026, 8, 28, 1, 5, 32)  # no tzinfo — deliberately
    with pytest.raises(ValueError) as err:
        utc_partition_date(naive)
    assert "NAIVE" in str(err.value)


def test_non_datetime_is_refused():
    with pytest.raises(TypeError):
        utc_partition_date("2026-08-28")


def test_aware_non_utc_input_is_converted_not_truncated():
    """An aware EDT datetime denotes an instant; the helper converts it to UTC.

    The same wall-clock reading in EDT and its UTC equivalent MUST partition
    identically — an instant is an instant regardless of the offset it is
    written in.
    """
    edt_written = datetime(2026, 8, 27, 21, 5, 32, tzinfo=EDT)
    utc_written = datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc)
    assert edt_written == utc_written  # same instant, different notation
    assert utc_partition_date(edt_written) == utc_partition_date(utc_written)
    assert utc_partition_date(edt_written) == "2026-08-28"


def test_shape_and_determinism():
    """The key shape is YYYY-MM-DD and the helper is a pure function."""
    instant = datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc)
    first = utc_partition_date(instant)
    assert first == utc_partition_date(instant)  # no hidden state, no wall clock
    assert len(first) == 10
    assert first[4] == first[7] == "-"
    datetime.strptime(first, "%Y-%m-%d")  # parses as a date or raises


def test_declared_clock_is_citable_as_data():
    """The ruled clock is readable without parsing the function body."""
    assert partition_key.PARTITION_CLOCK == "UTC"
    assert partition_key.PARTITION_DATE_FORMAT == "%Y-%m-%d"


def test_default_argument_reads_the_utc_clock():
    """Omitting `now` reads UTC — bounded assertion, no wall-clock equality.

    Asserts only that the default path returns a well-shaped key matching the
    UTC date of an instant sampled around it, never an exact equality against
    a moving clock.
    """
    before = datetime.now(timezone.utc)
    produced = utc_partition_date()
    after = datetime.now(timezone.utc)
    assert produced in {utc_partition_date(before), utc_partition_date(after)}
