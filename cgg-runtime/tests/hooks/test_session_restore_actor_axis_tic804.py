#!/usr/bin/env python3
"""SessionStart seam actor axis — "refuse one, declare three" (tic 803 -> 804).

Guards the ruled increment in cgg-runtime/hooks/session-restore.sh
(/review 803 round 2, Ruling B, Architect-ratified, recommended option verbatim
"Refuse one, declare three"; receipt
audit-logs/governance/receipts/2026-09-19-tic803-seam-primary-only-acts-ruling.md).

Four acts fire on the SessionStart seam. Exactly ONE of them is refused for a
non-primary actor:

  ACT 1  mandate auto-write + trigger-router route  -> REFUSED (non-idempotent,
                                                       authority-bearing)
  ACT 2  CPR gate-advance reconciler                -> actor-agnostic
                                                       (deterministic)
  ACT 3  inbox sweeps (ent_homeskillet, ent_mogul)  -> actor-agnostic
                                                       (idempotent)
  ACT 4  cpr-extract backfill                       -> actor-agnostic
                                                       (dedup at write)

ONE RULE, TWO CALL SITES: session-restore.sh does not re-implement the actor
rule; it imports `derive_actor` from cgg-runtime/hooks/cadence-handoff-seal.py,
the same function `handle_reconcile_at_start` already uses. That file is READ
by this increment and never written.

THE FOURTH ACTOR KIND. A headless `claude -p` child that boots WITHOUT the
runner's exported CGG_OBLIGATION_MANDATE_ID is TYPED AS THE PRIMARY -- and is
therefore admitted, not refused. That is not an oversight: the rule's
discriminator is the PRESENCE of the obligation environment, and it is its
ABSENCE that makes the primary the primary (cadence-handoff-seal.py's own
lock line: "whoever boots first is not thereby the primary; the seal asks
who"). A child spawned without the export carries no evidence at this seam
that it is a child. test_fourth_actor_kind_headless_without_obligation_is_
typed_primary pins that behaviour as DECLARED, so a future reader meets a
recorded decision rather than a silent hole.

EVIDENCE CLASS: FIXTURE-green. Every run here executes the hook against a
tempfile fixture zone pinned via CLAUDE_PROJECT_DIR, with HOME redirected to a
fixture and every resolve_script target shadowed by a stub in
<zone>/scripts/ (resolution priority 1). No real mandate is written, no real
trigger routed, no real queue or inbox touched. Fixture-green is NOT live-green,
and source-green is NOT installed-green on this seam: SessionStart execs an
INSTALLED copy via ~/.claude/hooks/session-restore-patch.sh.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT rule or cure which promoter is the seal seam's ordinary path (that is the tic-801 born, adjudicated at /review 804), does NOT add coverage for the seal hook's PreToolUse stage path, its PostToolUse promoter or its plan-capture identity validator (F-802-B1's residue), and does NOT prove that the obligation variable reaches the SessionStart hook process — that leg remains reasoned from shared parentage until a live refusal row witnesses it.
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
RUNTIME = HERE.parent.parent
HOOKS = RUNTIME / "hooks"
PLUGIN_ROOT = RUNTIME.parent

# Overridable so the NEGATIVE CONTROL can point at a reverted scratch copy
# OUTSIDE the measured tree without editing this file.
SESSION_RESTORE = pathlib.Path(
    os.environ.get("SESSION_RESTORE_UNDER_TEST") or (HOOKS / "session-restore.sh")
)
SEAL_HOOK = HOOKS / "cadence-handoff-seal.py"

TIC = 804
MANDATE_ID = "tic-804-20260919T115959"

# Every resolve_script target the hook can reach, stubbed. A stub records its
# argv and exits 0, so no real governance script ever runs under test.
STUB_PY = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["CGG_STUB_LOG"], "a") as fh:
    fh.write(json.dumps({"script": %r, "argv": sys.argv[1:]}) + "\\n")
out = %r
if out:
    print(out)
"""

STUBS = {
    "cpr-extract.py": "",
    "cpr-gate-advance.py": "",
    "cpr-enrichment-scanner.py": "",
    "trigger-router.py": json.dumps({"status": "routed"}),
    "mandate-write.py": json.dumps(
        {"mandate_id": MANDATE_ID, "cycle_request": {"run_now": ["queue_refresh"]}}
    ),
    "inbox-envelope.py": "",
    "inbox-query.py": "",
    "crisis-injection.py": "",
    "boot-injection.py": "",
    "office-worldview.py": "",
    "midtic-note.py": "",
}


def _make_zone(tmp_path, mandate_tic=None):
    """Isolated zone + isolated HOME. Nothing here touches the real federation."""
    zone = tmp_path / "zone"
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    zone.mkdir()
    (zone / ".ticzone").write_text("{}")

    for rel in ("audit-logs/hooks", "audit-logs/tics", "audit-logs/cprs",
                "audit-logs/mogul/mandates/history", "audit-logs/signals",
                "scripts"):
        (zone / rel).mkdir(parents=True, exist_ok=True)

    # Tic authority — act 1 is reachable only when TIC_COUNT > 0.
    (zone / "audit-logs/tics/tics.jsonl").write_text(json.dumps({
        "type": "tic", "count_mode": "counted", "global_counter_after": TIC
    }) + "\n")

    # One non-terminal queue row so TOTAL_CPRS > 0 and ACT 4 is reachable.
    (zone / "audit-logs/cprs/queue.jsonl").write_text(json.dumps({
        "id": "cpr_fixture_804", "status": "extracted", "birth_tic": 800,
    }) + "\n")

    # MANDATE_ALREADY_EXISTS must be false for act 1 to be live.
    if mandate_tic is not None:
        (zone / "audit-logs/mogul/mandates/current.json").write_text(
            json.dumps({"tic_context": {"current_tic": mandate_tic}})
        )

    for name, out in STUBS.items():
        p = zone / "scripts" / name
        p.write_text(STUB_PY % (name, out))
        p.chmod(0o755)
    return zone, home


def _boot(zone, home, agent_id="", mandate_id=None, obligation_tic=None):
    """Run the REAL hook against the FIXTURE zone only."""
    stub_log = zone / "stub-calls.jsonl"
    env = dict(os.environ)
    for k in ("CGG_OBLIGATION_MANDATE_ID", "CGG_OBLIGATION_TIC"):
        env.pop(k, None)
    env.update({
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(zone),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CGG_STUB_LOG": str(stub_log),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    if mandate_id is not None:
        env["CGG_OBLIGATION_MANDATE_ID"] = mandate_id
    if obligation_tic is not None:
        env["CGG_OBLIGATION_TIC"] = obligation_tic

    payload = json.dumps({"agent_id": agent_id, "agent_type": "general" if agent_id else ""})
    r = subprocess.run(["bash", str(SESSION_RESTORE)], input=payload,
                       capture_output=True, text=True, env=env, cwd=str(zone))
    calls = []
    if stub_log.is_file():
        calls = [json.loads(x) for x in stub_log.read_text().splitlines() if x.strip()]
    return r, calls


def _called(calls, script, *must_contain):
    for c in calls:
        if c["script"] != script:
            continue
        argv = " ".join(c["argv"])
        if all(m in argv for m in must_contain):
            return True
    return False


def _refusals(zone):
    p = zone / "audit-logs" / "hooks" / "boot-act-refusals.jsonl"
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _mandate_written(zone):
    return (zone / "audit-logs" / "mogul" / "mandates" / "current.json").exists()


# ---------------------------------------------------------------------------
# ACTOR KIND 1 — the PRIMARY. Act 1 fires exactly as before the cure.
# ---------------------------------------------------------------------------

def test_primary_still_writes_and_routes_the_mandate(tmp_path):
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id="")

    assert r.returncode == 0, r.stderr
    assert _called(calls, "trigger-router.py", "route", "mogul.mandate"), \
        "the primary must still ROUTE its mandate"
    assert _called(calls, "mandate-write.py", "--trigger-kind", "session_start"), \
        "the primary must still WRITE its mandate"
    assert _refusals(zone) == [], "the primary must never journal a refusal"


def test_primary_cannot_be_locked_out_under_the_measured_empty_agent_id(tmp_path):
    """The tic-802 build measured EVERY journal row carrying an EMPTY agent_id.

    Under exactly that condition -- empty agent_id, no obligation environment --
    the primary's act-1 path must be unchanged in behaviour by this cure.
    """
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id="")  # the measured condition, verbatim

    assert r.returncode == 0, r.stderr
    assert _called(calls, "trigger-router.py", "route")
    assert _called(calls, "mandate-write.py")
    assert _refusals(zone) == []


def test_primary_runs_all_four_acts(tmp_path):
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id="")

    assert r.returncode == 0, r.stderr
    assert _called(calls, "cpr-extract.py"), "ACT 4"
    assert _called(calls, "cpr-gate-advance.py"), "ACT 2"
    assert _called(calls, "inbox-envelope.py", "sweep", "ent_homeskillet"), "ACT 3"
    assert _called(calls, "inbox-envelope.py", "sweep", "ent_mogul"), "ACT 3"
    assert _called(calls, "trigger-router.py", "route"), "ACT 1"


# ---------------------------------------------------------------------------
# ACTOR KIND 2 — a SubagentStart citizen context reaching this seam.
# ACTOR KIND 3 — a headless `claude -p` child WITH the obligation export.
# Both are non-primary: ACT 1 refused, acts 2/3/4 still run, boot continues.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind,agent_id,mandate_id,expect_actor,expect_class", [
    ("subagent", "agent_citizen_804", None,
     "subagent:agent_citizen_804", "subagent"),
    ("headless_citizen", "", MANDATE_ID,
     "headless_citizen:" + MANDATE_ID, "headless_citizen"),
])
def test_non_primary_actor_is_refused_act1(tmp_path, kind, agent_id, mandate_id,
                                           expect_actor, expect_class):
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id=agent_id, mandate_id=mandate_id,
                     obligation_tic="804" if mandate_id else None)

    assert r.returncode == 0, r.stderr
    # ACT 1 REFUSED — nothing written, nothing routed.
    assert not _called(calls, "trigger-router.py", "route"), \
        "%s must NOT route a mandate" % kind
    assert not _called(calls, "mandate-write.py"), \
        "%s must NOT write a mandate" % kind
    assert not _mandate_written(zone), \
        "%s must leave current.json absent" % kind

    # ...and the refusal is JOURNALED, typed, naming the actor.
    rows = _refusals(zone)
    assert len(rows) == 1, "exactly ONE refusal row; got %d" % len(rows)
    row = rows[0]
    assert row["journal_event"] == "mandate_write_refused"
    assert row["reason"] == "non_primary_actor"
    assert row["actor"] == expect_actor
    assert row["actor_class"] == expect_class
    assert row["act"] == "mandate_auto_write_and_trigger_router_route"
    assert row["tic"] == TIC
    assert row["at"]


@pytest.mark.parametrize("kind,agent_id,mandate_id", [
    ("subagent", "agent_citizen_804", None),
    ("headless_citizen", "", MANDATE_ID),
])
def test_boot_continues_acts_2_3_4_still_run_for_a_refused_actor(
        tmp_path, kind, agent_id, mandate_id):
    """The refusal is ONE act, not a boot abort. This is the ruling's core shape."""
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id=agent_id, mandate_id=mandate_id)

    assert r.returncode == 0, "the boot must CONTINUE after a refusal"
    assert _called(calls, "cpr-extract.py"), \
        "ACT 4 (dedup at write) must still run for %s" % kind
    assert _called(calls, "cpr-gate-advance.py"), \
        "ACT 2 (deterministic) must still run for %s" % kind
    assert _called(calls, "inbox-envelope.py", "sweep", "ent_homeskillet"), \
        "ACT 3 (idempotent) must still run for %s" % kind
    assert _called(calls, "inbox-envelope.py", "sweep", "ent_mogul"), \
        "ACT 3 (idempotent) must still run for %s" % kind


def test_refused_boot_still_emits_its_sessionstart_payload(tmp_path):
    """A refusal must not silence the boot injection."""
    zone, home = _make_zone(tmp_path)
    r, _ = _boot(zone, home, agent_id="", mandate_id=MANDATE_ID)
    assert r.returncode == 0
    assert r.stdout.strip(), "the hook must still emit its context payload"
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_non_primary_writes_exactly_one_refusal_row_not_one_per_act(tmp_path):
    zone, home = _make_zone(tmp_path)
    _boot(zone, home, agent_id="", mandate_id=MANDATE_ID)
    assert len(_refusals(zone)) == 1


# ---------------------------------------------------------------------------
# ACTOR KIND 4 — a headless child WITHOUT the obligation export.
# TYPED AS THE PRIMARY. Declared, not silently held.
# ---------------------------------------------------------------------------

def test_fourth_actor_kind_headless_without_obligation_is_typed_primary(tmp_path):
    """The honest residual: absence of the discriminator IS the primary's mark.

    A `claude -p` child spawned without CGG_OBLIGATION_MANDATE_ID presents an
    empty agent_id and no obligation environment -- byte-for-byte the primary's
    shape at this seam. It is ADMITTED, and that is the rule working as ruled,
    not a leak: the obligation ids are a LABEL source, never trusted as
    authority, and it is their ABSENCE that makes the primary the primary. The
    residual is closed only by the runner exporting the variable (it does) AND
    that variable reaching the hook process -- which this increment does NOT
    prove.
    """
    zone, home = _make_zone(tmp_path)
    r, calls = _boot(zone, home, agent_id="", mandate_id=None)

    assert r.returncode == 0, r.stderr
    assert _refusals(zone) == [], \
        "no discriminator is present, so there is nothing to refuse ON"
    assert _called(calls, "trigger-router.py", "route"), \
        "this kind is TYPED PRIMARY and is admitted -- declared, not silent"


# ---------------------------------------------------------------------------
# ONE RULE, TWO CALL SITES — structural guards
# ---------------------------------------------------------------------------

def test_actor_rule_is_imported_from_the_seal_never_reimplemented():
    text = SESSION_RESTORE.read_text()
    assert "derive_actor" in text, "the hook must call the seal's rule"
    assert 'spec_from_file_location("cgg_seal_rule"' in text, \
        "the rule must be IMPORTED from cadence-handoff-seal.py, not re-derived"
    # A second bash-side implementation would be a SECOND RULE.
    for smell in ("CGG_OBLIGATION_MANDATE_ID}", 'if [ -n "$CGG_OBLIGATION_MANDATE_ID" ]'):
        assert smell not in text, \
            "session-restore.sh must not re-derive the actor in bash (%s)" % smell


def test_both_call_sites_reach_the_same_derive_actor():
    """One rule, two call sites — proved by execution, not by prose."""
    seal = SEAL_HOOK.read_text()
    assert "def derive_actor(" in seal, "call site A's rule lives here"
    assert "derive_actor(agent_id)" in seal, "call site A: handle_reconcile_at_start"

    import importlib.util
    spec = importlib.util.spec_from_file_location("cgg_seal_rule_probe", SEAL_HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    saved = {k: os.environ.get(k) for k in ("CGG_OBLIGATION_MANDATE_ID", "CGG_OBLIGATION_TIC")}
    try:
        os.environ.pop("CGG_OBLIGATION_MANDATE_ID", None)
        os.environ.pop("CGG_OBLIGATION_TIC", None)
        assert mod.derive_actor("")["is_primary"] is True
        assert mod.derive_actor("a1")["actor_class"] == "subagent"
        os.environ["CGG_OBLIGATION_MANDATE_ID"] = MANDATE_ID
        assert mod.derive_actor("")["actor"] == "headless_citizen:" + MANDATE_ID
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_derivation_fails_open_to_primary():
    """A derivation fault must never lock the primary out of its own lane."""
    text = SESSION_RESTORE.read_text()
    assert 'BOOT_ACTOR_IS_PRIMARY="true"' in text, "the default must be primary"
    # Refusal fires ONLY on an explicit "false"; the admit guard on anything else.
    assert '[ "$BOOT_ACTOR_IS_PRIMARY" = "false" ]' in text
    assert '[ "$BOOT_ACTOR_IS_PRIMARY" != "false" ]' in text


# ---------------------------------------------------------------------------
# The three in-place DECLARATIONS and the corrected comment
# ---------------------------------------------------------------------------

def _decommented(text):
    """Strip comment prefixes and collapse whitespace.

    The three DECLARATIONS are prose comments and may lawfully wrap across
    `#`-prefixed lines -- only the RIDER must be one contiguous unit. A
    line-naive `in` check therefore tests the line break, not the predicate.
    Normalize first, then pin the predicate's site.
    """
    lines = []
    for line in text.splitlines():
        s = line.strip()
        lines.append(s[1:].strip() if s.startswith("#") else s)
    return " ".join(" ".join(lines).split())


def test_acts_2_3_4_carry_an_in_place_declaration_with_its_reason():
    text = SESSION_RESTORE.read_text()
    flat = _decommented(text)
    assert text.count("ACTOR-AGNOSTIC BY DESIGN") == 3, \
        "exactly three acts are declared actor-agnostic in place"
    assert "REASON: DETERMINISTIC" in flat, "ACT 2's reason"
    assert "REASON: IDEMPOTENT" in flat, "ACT 3's reason"
    assert "REASON: DEDUP AT WRITE" in flat, "ACT 4's reason"
    for act in ("ACT 2 of 4", "ACT 3 of 4", "ACT 4 of 4", "ACT 1 of 4"):
        assert act in text, "%s must name itself at its call site" % act


def test_false_primary_only_comment_is_corrected_to_name_three_boot_kinds():
    text = SESSION_RESTORE.read_text()
    assert "Primary-only: this fires from the" not in text, \
        "the false Primary-only claim must be gone"
    assert "SessionStart-seam-only, which is" in text
    assert "NOT the same as primary-only" in text
    for kind in ("PRIMARY orchestrator", "SubagentStart CITIZEN", "HEADLESS `claude -p` child"):
        assert kind in text, "the corrected comment must name %s" % kind


def test_does_not_satisfy_rider_travels_verbatim_as_one_contiguous_unit():
    """A rider wrapped across comment-prefix lines does not exist as a unit."""
    rider = (
        "this increment does NOT rule or cure which promoter is the seal seam's "
        "ordinary path (that is the tic-801 born, adjudicated at /review 804), "
        "does NOT add coverage for the seal hook's PreToolUse stage path, its "
        "PostToolUse promoter or its plan-capture identity validator (F-802-B1's "
        "residue), and does NOT prove that the obligation variable reaches the "
        "SessionStart hook process — that leg remains reasoned from shared "
        "parentage until a live refusal row witnesses it."
    )
    text = SESSION_RESTORE.read_text()
    assert rider in text, "the rider must appear VERBATIM and CONTIGUOUS"
    # ...and on a single line, not wrapped across `#` prefixes.
    assert any(rider in line for line in text.splitlines()), \
        "the rider must be ONE contiguous line, never wrapped"


def test_seal_hook_is_untouched_by_this_increment():
    """cadence-handoff-seal.py is READ for the rule and never written."""
    seal = SEAL_HOOK.read_text()
    assert "mandate_write_refused" not in seal, \
        "the act-1 refusal must not have been added to the seal hook"
    assert "boot-act-refusals" not in seal


def test_refusal_journal_is_a_sibling_never_the_seals_journal(tmp_path):
    """Two lifecycles must not share one journal."""
    zone, home = _make_zone(tmp_path)
    _boot(zone, home, agent_id="", mandate_id=MANDATE_ID)
    assert (zone / "audit-logs/hooks/boot-act-refusals.jsonl").is_file()
    assert not (zone / "audit-logs/hooks/handoff-seals.jsonl").is_file(), \
        "the act-1 refusal must not pollute the seal's own journal"
