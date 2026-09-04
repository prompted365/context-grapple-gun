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


# =============================================================================
# ARM 5 — THE JOIN (wave 5b, /review 767 round 3)
#
# The staged patch's own proof obligation, quoted: "A negative control on the
# JOIN, not on one writer: inject an instant inside the window and assert all
# three writers name the SAME file."
#
# This is the arm that tests the ATOM. Arms 1-4 prove the primitive is correct;
# they would all stay green while the mandates/history lane was split across
# three writers, because none of them looks at a writer. The defect this
# increment cures is not "a function returns the wrong date" — it is "writers
# into ONE file disagree about its name." Only a join assertion can see that.
#
# Two halves, both load-bearing:
#   (a) BEHAVIOURAL — the python derivation, the shell derivation, and the
#       reader's derivation all produce the SAME key at an in-window instant.
#   (b) STRUCTURAL  — the three writer sites ON DISK are pinned to that clock.
#       (a) alone would stay green if a writer were reverted tomorrow, because
#       (a) never reads the writers. (b) is the regression guard: revert ANY
#       one of the three and it fails by name.
# =============================================================================

import subprocess

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_CGG_RUNTIME = os.path.dirname(_SCRIPTS)

# The closed writer set into audit-logs/mogul/mandates/history/<date>.jsonl,
# measured tic 767. THREE writers — the pre-cure crisis-injection.py docstring
# said "BOTH of its writers" and named two; it did not know about the runner.
_MANDATES_HISTORY_WRITERS = {
    "mandate-write.py": os.path.join(_SCRIPTS, "mandate-write.py"),
    "mogul-runner.sh": os.path.join(_SCRIPTS, "mogul-runner.sh"),
    "session-restore.sh": os.path.join(_CGG_RUNTIME, "hooks", "session-restore.sh"),
}


def _shell_utc_partition_date(instant):
    """Run the SHELL writers' actual derivation (`date -u +%Y-%m-%d`) at an
    injected instant. BSD (`-r EPOCH`) then GNU (`-d @EPOCH`); skip if neither."""
    epoch = str(int(instant.timestamp()))
    for args in (["date", "-u", "-r", epoch, "+%Y-%m-%d"],
                 ["date", "-u", "-d", "@" + epoch, "+%Y-%m-%d"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    pytest.skip("no date(1) supporting instant injection (-r or -d @EPOCH)")


def _shell_local_partition_date(instant):
    """The PRE-CURE shell derivation (`date +%Y-%m-%d`, no -u) at the same
    instant — the discriminating control."""
    epoch = str(int(instant.timestamp()))
    for args in (["date", "-r", epoch, "+%Y-%m-%d"],
                 ["date", "-d", "@" + epoch, "+%Y-%m-%d"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=10,
                                 env={**os.environ, "TZ": "America/New_York"})
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    pytest.skip("no date(1) supporting instant injection (-r or -d @EPOCH)")


@pytest.mark.parametrize("instant,expected", [
    (datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc), "2026-08-28"),
    (datetime(2026, 8, 28, 2, 0, tzinfo=timezone.utc), "2026-08-28"),
    (datetime(2026, 8, 28, 3, 59, 59, tzinfo=timezone.utc), "2026-08-28"),
])
def test_join_all_three_writers_and_the_reader_name_the_same_file(instant, expected):
    """THE JOIN. At an in-window instant every leg of the atom agrees."""
    python_writer = utc_partition_date(instant)          # mandate-write.py:416
    shell_writer = _shell_utc_partition_date(instant)    # runner :317 + session-restore :831
    keys = {python_writer, shell_writer}
    assert keys == {expected}, (
        "the mandates/history partition key SPLIT across the writer set: "
        f"python={python_writer!r} shell={shell_writer!r}"
    )
    assert len(keys) == 1, "one lane, one file name, one clock"


@pytest.mark.parametrize("instant", [
    datetime(2026, 8, 28, 1, 5, 32, tzinfo=timezone.utc),
    datetime(2026, 8, 28, 2, 0, tzinfo=timezone.utc),
])
def test_join_negative_control_the_precure_shell_clock_splits_the_lane(instant):
    """The discriminating half: revert the SHELL leg to its pre-cure form and
    the join breaks at the same instants. If this ever stops failing, the
    divergence being modelled is gone and the arm above is a tautology."""
    cured = utc_partition_date(instant)
    precure_shell = _shell_local_partition_date(instant)
    assert precure_shell != cured, (
        "the pre-cure local shell derivation must DISAGREE with the ruled clock "
        f"inside the window (got {precure_shell!r} == {cured!r}); if this passes, "
        "the machine's local zone is UTC and this control cannot discriminate here"
    )
    assert len({cured, precure_shell}) == 2, "this is the split the cure removes"


def test_join_outside_the_window_the_precure_clock_agreed_which_is_why_it_survived():
    """Scope honesty: a local writer is right ~83% of the day on a UTC-4 zone."""
    instant = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)  # 12:00 EDT
    assert _shell_local_partition_date(instant) == utc_partition_date(instant)


@pytest.mark.parametrize("name,path", sorted(_MANDATES_HISTORY_WRITERS.items()))
def test_structural_every_mandates_history_writer_is_pinned_to_the_ruled_clock(name, path):
    """REGRESSION GUARD: revert any ONE writer and this fails BY NAME.

    The behavioural join above never reads the writers, so it would stay green
    through a revert. This arm is what makes the atom hold over time.
    """
    src = open(path, encoding="utf-8").read()
    if name == "mandate-write.py":
        assert "from lib.partition_key import utc_partition_date" in src
        assert "today = utc_partition_date()" in src
        assert 'today = datetime.now().strftime("%Y-%m-%d")' not in src, (
            "mandate-write.py reverted to the LOCAL clock — the lane is split")
    else:
        assert "TODAY=$(date -u +%Y-%m-%d)" in src, f"{name} is not on the ruled clock"
        assert "TODAY=$(date +%Y-%m-%d)" not in src, (
            f"{name} reverted to the LOCAL clock — the lane is split")


def test_structural_the_reader_moved_with_its_writers():
    """The fourth surface. A cured writer set with a local reader re-opens F-745
    at the other end — the reader is not optional."""
    src = open(os.path.join(_SCRIPTS, "crisis-injection.py"), encoding="utf-8").read()
    assert "today = _utc_today(now)" in src
    assert "def _local_today" not in src, (
        "_local_today() survived the cure; its documented rationale is now false")
    assert "return date.today().isoformat()" not in src


def test_structural_the_writer_census_is_three_not_two():
    """The under-count that produced the wrong 'deliberately local' decision.

    The retired docstring said "BOTH of its writers" and named TWO. This pins
    the corrected census so the error cannot silently return.
    """
    assert len(_MANDATES_HISTORY_WRITERS) == 3
    for path in _MANDATES_HISTORY_WRITERS.values():
        assert os.path.isfile(path), path


# =============================================================================
# ARM 6 — THE tics/ LANE (OM-4, B2 wave 8, /review 770 round 2 Q5)
#
# Arm 5 pinned the mandates/history lane. This arm pins the OTHER half of the
# t745 pair — the audit-logs/tics/<date>.jsonl lane — the same way, because the
# t745 defect was a BROKEN JOIN BETWEEN THE TWO: one emission, one instant, two
# differently-dated files. Pinning one side and not the other leaves the join
# provable from only one end.
#
# PREVENTIVE, NOT RESTORATIVE — stated at composition, not discovered later:
# BOTH tics/ partition sites were ALREADY on the UTC clock before this wave, so
# ZERO emissions change date and no historical file is affected. What the merge
# removes is the LATENT re-opening: an inline derivation is one careless edit
# away from the local clock, and nothing on disk would have caught it. That is
# also why the structural half below is the load-bearing half here — the
# behavioural half cannot fail today even if a writer is reverted, because the
# reverted form is still UTC. Only a source-level pin can see this regression.
#
# CENSUS CORRECTION (F-770-W8A-1, measured at build): the wave-8 evidence brief
# tabled THREE tics/ derivations and named cadence-ops.py ~:663 as the second.
# Read at HEAD de53d8c, that site's `now` has exactly ONE consumer —
# `"snapshot_at": now.isoformat()` — and its function writes
# conformations/tic-<N>.json, a TIC-NUMBERED path. It derives no dated
# partition filename, so under the ruling's own discriminator ("only the sites
# that derive a DATED PARTITION FILENAME for audit-logs/tics/ move; a timestamp
# derivation that is not a partition key stays") it STAYS. The partition-writer
# set is TWO. Both the corrected census and the excluded timestamp sites are
# pinned below so the over-count cannot silently return — and so no future
# citizen "completes" the merge by migrating a timestamp.
# =============================================================================

# The closed PARTITION-writer set into audit-logs/tics/<date>.jsonl, measured
# tic 770 at CGG HEAD de53d8c. TWO sites — see the census correction above.
_TICS_LANE_PARTITION_WRITERS = {
    "cadence-ops.py": os.path.join(_SCRIPTS, "cadence-ops.py"),
    "rebru-cadence-emit.py": os.path.join(_SCRIPTS, "rebru-cadence-emit.py"),
}

# Sites in the SAME two files that derive a TIMESTAMP, not a partition key, and
# are therefore DELIBERATELY out of the merge. Each entry is
# (file, must-still-contain, why-it-is-not-a-partition-key).
_TICS_LANE_EXCLUDED_TIMESTAMP_SITES = [
    (
        "cadence-ops.py",
        '"snapshot_at": now.isoformat(),',
        "write_conformation's snapshot instant; its artifact is "
        "conformations/tic-<N>.json — tic-numbered, never dated",
    ),
    (
        "cadence-ops.py",
        'now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")',
        "the tic event row's own ISO-8601 `tic` field — a full timestamp, "
        "not a daily key",
    ),
    (
        "rebru-cadence-emit.py",
        'emit_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")',
        "the cadence block's emission_at timestamp — not a filename",
    ),
]


# --- ARM 6a: BEHAVIOURAL — the tics/ lane joins mandates/history -------------

@pytest.mark.parametrize("instant,expected_utc,expected_local", DIVERGENCE_WINDOW)
def test_tics_lane_and_mandates_history_name_the_same_date(instant, expected_utc,
                                                           expected_local):
    """THE t745 JOIN, both ends now derived through the one helper.

    On disk at t745 this instant produced tics/2026-08-28.jsonl AND
    mandates/history/2026-08-27.jsonl. Through the shared clock both lanes
    name ONE date, so a consumer joining tics/<date> against
    mandates/history/<date> cannot lose the boundary.
    """
    tics_lane = utc_partition_date(instant)            # cadence-ops.py emit_tic
    rebru_pointer = utc_partition_date(instant)        # rebru-cadence-emit @Tic.0
    mandates_history = utc_partition_date(instant)     # mandate-write.py

    assert {tics_lane, rebru_pointer, mandates_history} == {expected_utc}, (
        "the t745 JOIN split across the lanes: "
        f"tics={tics_lane!r} rebru={rebru_pointer!r} "
        f"mandates_history={mandates_history!r}"
    )
    # And the pre-cure local clock still names the OTHER file — the control
    # that keeps this assertion from being a tautology.
    assert local_clock_partition_date(instant) == expected_local
    assert local_clock_partition_date(instant) != tics_lane


@pytest.mark.parametrize("instant,expected_utc,expected_local", DIVERGENCE_WINDOW)
def test_retired_inline_slice_is_byte_equal_to_the_helper(instant, expected_utc,
                                                          expected_local):
    """PREVENTIVE-NOT-RESTORATIVE, proven rather than asserted in prose.

    cadence-ops.py derived its key as `now.strftime("%Y-%m-%dT%H:%M:%SZ")[:10]`
    and rebru-cadence-emit.py as `.strftime("%Y-%m-%d")`. Both were ALREADY
    UTC. This pins that the migration changes ZERO output on every instant in
    the divergence window — so "no behaviour change" is a measurement, not a
    claim, and any future drift in the helper is caught against the exact form
    the tics/ lane used to emit.
    """
    retired_cadence_ops = instant.strftime("%Y-%m-%dT%H:%M:%SZ")[:10]
    retired_rebru = instant.strftime("%Y-%m-%d")
    cured = utc_partition_date(instant)

    assert retired_cadence_ops == cured, (
        "the cadence-ops migration CHANGED the emitted partition key — this "
        "increment was ruled preventive-not-restorative and must not move a date"
    )
    assert retired_rebru == cured, (
        "the rebru-cadence-emit migration CHANGED the emitted partition key"
    )
    assert cured == expected_utc


# --- ARM 6b: STRUCTURAL — the load-bearing half for THIS lane ----------------

@pytest.mark.parametrize("name,path", sorted(_TICS_LANE_PARTITION_WRITERS.items()))
def test_structural_every_tics_lane_writer_is_pinned_to_the_ruled_clock(name, path):
    """REGRESSION GUARD: revert either tics/ writer and this fails BY NAME.

    THE load-bearing arm for this lane. Because both sites were already UTC, a
    revert to the inline form is BEHAVIOURALLY INVISIBLE — arm 6a would stay
    green through it. Only this source-level pin can see the lane fragmenting
    again, which is precisely the latent class the merge was ruled to close.
    """
    src = open(path, encoding="utf-8").read()
    assert "from lib.partition_key import utc_partition_date" in src, (
        f"{name} does not import the shared clock — the tics/ lane is split")

    if name == "cadence-ops.py":
        assert "today = utc_partition_date(now)" in src, (
            "cadence-ops.py no longer derives the tics/ partition key through "
            "the shared clock")
        assert "today = now_iso[:10]" not in src, (
            "cadence-ops.py reverted to the INLINE slice derivation — the "
            "tics/ lane is one careless edit from the local clock again")
        # The key must still be what NAMES the file, or the pin above is
        # pinning a variable nothing reads.
        assert 'tic_file = os.path.join(tic_dir, f"{today}.jsonl")' in src, (
            "cadence-ops.py no longer composes the tics/ filename from `today` "
            "— this pin has gone vacuous and must be re-aimed")
        # The instant must be passed EXPLICITLY: a bare utc_partition_date()
        # here would read the wall clock a SECOND time, and an emission that
        # straddles midnight would name a file whose date disagrees with the
        # `tic` timestamp in the row it holds — the t745 shape, inside one
        # emission.
        assert "today = utc_partition_date()" not in src, (
            "cadence-ops.py dropped the explicit instant — the file name and "
            "the row's own timestamp can now be derived from two reads")
    else:
        assert "today = utc_partition_date()" in src, (
            "rebru-cadence-emit.py no longer derives its tics/ pointer through "
            "the shared clock")
        assert 'today = datetime.now(timezone.utc).strftime("%Y-%m-%d")' not in src, (
            "rebru-cadence-emit.py reverted to the INLINE derivation")
        assert 'f"audit-logs/tics/{today}.jsonl"' in src, (
            "rebru-cadence-emit.py no longer names the tics/ partition from "
            "`today` — this pin has gone vacuous and must be re-aimed")


@pytest.mark.parametrize("name,needle,why", _TICS_LANE_EXCLUDED_TIMESTAMP_SITES)
def test_structural_excluded_timestamp_sites_stay_inline(name, needle, why):
    """The RIDER, enforced: a timestamp derivation is NOT a partition key.

    The merge was fenced to derivations that name a DATED PARTITION FILENAME.
    These three sites derive timestamps and were deliberately left inline; a
    future citizen "finishing the job" by routing them through the daily-key
    helper would be truncating a timestamp to a date, which is a behaviour
    change this ruling did not authorize. Failing here means the fence moved.
    """
    src = open(_TICS_LANE_PARTITION_WRITERS[name], encoding="utf-8").read()
    assert needle in src, (
        f"{name}: an EXCLUDED timestamp site changed — {why}. The wave-8 fence "
        "covered partition keys only; moving this needs its own ruling.")


def test_structural_the_tics_partition_writer_census_is_two_not_three():
    """F-770-W8A-1 pinned: the over-count that would re-enter as a 'gap'.

    The evidence brief tabled THREE tics/ derivations; the third
    (cadence-ops.py ~:663) derives `snapshot_at` for a TIC-NUMBERED artifact
    and is not a partition key at all. Pinning the corrected census — and the
    tic-numbered conformation path that proves it — stops the over-count from
    returning as a future 'unmerged site' finding.
    """
    assert len(_TICS_LANE_PARTITION_WRITERS) == 2
    for path in _TICS_LANE_PARTITION_WRITERS.values():
        assert os.path.isfile(path), path

    cadence_ops = open(_TICS_LANE_PARTITION_WRITERS["cadence-ops.py"],
                       encoding="utf-8").read()
    # The evidence: write_conformation's artifact is tic-numbered, not dated.
    assert 'conf_path = os.path.join(conf_dir, f"tic-{tic_count}.json")' in cadence_ops, (
        "the conformation path is no longer tic-numbered — if it became dated, "
        "it BECAME a partition writer and owes this atom a migration")
