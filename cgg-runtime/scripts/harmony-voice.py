#!/usr/bin/env python3
"""
harmony-voice.py — bounded-morphism ambient voice proposer (cable BR5,
braid covenant tic 569; SPEC §BR5.2 + AMENDMENT-1 §4 + AMENDMENT-2 §5).

The LLM here is ψ_j — a PROPOSAL map, not an authority (foundation §13:
models are bounded morphism-proposers). Governance admits the proposal:
α_j = the validators below; ρ_j = the receipt (the voice object carrying
model / duration / validators / fallback_reason). A proposal that fails
any validator is refused and the lane falls back to the engine's canned
template — HONESTLY reported, never faked.

Contract:
  - NON-CITABLE ambient voice: a disposition that gets quoted verbatim has
    failed its mission — it shapes, it never instructs.
  - Wisdom expresses NATURALLY (KAT/TEL register — what is, what it serves);
    caution expresses APOPHATICALLY ONLY when the braid's epsilon_gate fired
    (AMD-1 §4.1 — the mathematical form of "not bound to warnings alone").
  - The voice must never render a composite certainty the slice did not
    carry (AMD-2 §5) — the prompt receives the slice's narrowed_to +
    renarrow_triggers as grounding.
  - Kill switch: HARMONY_VOICE=off skips the LLM entirely.
  - Headless call: `claude -p` with model ${HARMONY_VOICE_MODEL:-sonnet},
    --max-turns 1, 45s subprocess timeout.

Writes the `voice` object INTO disposition-tic-N.json (additive field,
audit-logs/harmony/ surface only) and prints it on stdout.

The LLM call is an explicitly-bounded IO seam (`runner` parameter) —
isolated and mockable; the __main__ selftest never performs network IO.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root  # noqa: E402


def _resolve_repo_root() -> pathlib.Path:
    env_override = os.environ.get("CGG_REPO_ROOT")
    if env_override:
        return pathlib.Path(env_override)
    try:
        return pathlib.Path(resolve_zone_root())
    except Exception:
        return pathlib.Path("/Users/breydentaylor/canonical")


REPO_ROOT = _resolve_repo_root()
HARMONY_DIR = REPO_ROOT / "audit-logs" / "harmony"
BRAID_DIR = REPO_ROOT / "audit-logs" / "braid"

MAX_CHARS = 240
LLM_TIMEOUT_S = 45
DEFAULT_MODEL = "sonnet"

# ---------------------------------------------------------------------------
# Validators (α_j — the admission predicate). Extends the imperative-guard
# family from aesop_archetype_field._IMPERATIVE_RE (same whole-word core).
# Rejection routes to template fallback; over-blocking fails SAFE (fallback),
# never dangerous.
# ---------------------------------------------------------------------------

_IMPERATIVE_WORDS_RE = re.compile(
    r"\b(must|never|always|shall|do\s+not|don'?t)\b", re.IGNORECASE
)
# Leading bare-verb command heuristic (SPEC: "reject on leading verb commands").
_LEADING_COMMAND_VERBS = {
    "do", "stop", "avoid", "ensure", "remember", "note", "keep", "hold",
    "preserve", "refuse", "act", "beware", "consider", "prevent", "halt",
    "cease", "maintain", "inject", "make", "use", "watch", "guard", "listen",
    "stay", "be", "let", "take", "go", "wait", "check", "verify", "trust",
}
_FIRST_PERSON_PLAN_RE = re.compile(r"\bI\s+will\b|\bI'll\b", re.IGNORECASE)
# Governance-id quoting guard (non-citable: ids are receipts, not ambience).
_GOVERNANCE_ID_RE = re.compile(
    r"\b(cpr_[a-z0-9_]+|sig_[a-z0-9_]+|wrn_[a-z0-9_]+|cogpr[-_]?\d+|"
    r"harmony_ray_[0-9a-f]+|harmony_packet_[0-9a-f]+)\b",
    re.IGNORECASE,
)
# Doctrine-citation guard (shape, never cite doctrine surfaces).
_DOCTRINE_CITATION_RE = re.compile(
    r"CLAUDE\.md|MEMORY\.md|ledger\.md|\bKey Invariant\b|\b/review\b",
    re.IGNORECASE,
)
# Center-naming guard (foundation §5–7: the held-open center is not a value
# any output may name, target, or serialize — Ω_center_capture).
_CENTER_NAMING_RE = re.compile(
    r"⊙|held[- ]open\s+cent(?:er|re)|founding\s+cent(?:er|re)", re.IGNORECASE
)


def validate_voice(line: str) -> tuple[bool, Optional[str]]:
    """Admission predicate over a proposed ambient line.

    Returns (ok, rejection_reason). The gate rejects:
      non-empty/whitespace-only · multi-line · >240 chars · imperative
      vocabulary (whole words) · leading bare-verb commands · first-person
      plans · governance-id quoting · doctrine citations · center-naming.
    """
    if not line or not line.strip():
        return False, "empty_output"
    stripped = line.strip()
    if "\n" in stripped or "\r" in stripped:
        return False, "multi_line"
    if len(stripped) > MAX_CHARS:
        return False, f"length_exceeds_{MAX_CHARS}"
    if _IMPERATIVE_WORDS_RE.search(stripped):
        return False, "imperative_vocabulary"
    first_word = re.split(r"[\s,.:;!—-]+", stripped.lstrip("\"'“”‘’ "), maxsplit=1)[0].lower()
    if first_word in _LEADING_COMMAND_VERBS:
        return False, "leading_verb_command"
    if _FIRST_PERSON_PLAN_RE.search(stripped):
        return False, "first_person_plan"
    if _GOVERNANCE_ID_RE.search(stripped):
        return False, "governance_id_quoted"
    if _DOCTRINE_CITATION_RE.search(stripped):
        return False, "doctrine_citation"
    if _CENTER_NAMING_RE.search(stripped):
        return False, "center_naming"
    return True, None


# ---------------------------------------------------------------------------
# Prompt construction (the constrained context handed to ψ_j).
# ---------------------------------------------------------------------------

def build_prompt(disposition: dict[str, Any], braid_packet: Optional[dict[str, Any]]) -> str:
    disp = disposition.get("disposition") or {}
    acoustic = disposition.get("acousticSignature") or {}
    stance = disp.get("stance", "idle")
    meaning_state = disposition.get("meaningState", "unknown")
    snr = acoustic.get("snr", 0.0)

    lines = [
        "You are the ambient voice layer of a governance runtime. Compose exactly",
        "ONE short observational line (under 200 characters, single line) that a",
        "person glancing at a status surface would absorb as atmosphere — wisdom",
        "overall, not warnings alone.",
        "",
        "Hard constraints on the line:",
        "- observational register only: describe, evoke, orient — the line may not",
        "  command, instruct, or prescribe (no imperative verbs, no 'must/never/",
        "  always/do not/don't/shall', no line that opens with a bare command verb)",
        "- no first-person plans ('I will', \"I'll\")",
        "- no identifiers, file names, doctrine references, or quoted rules",
        "- do not name or allude to any 'center' of the system",
        "- do not express more certainty than the terrain below carries",
        "- open with an article, noun, or scene — e.g. 'The ...', 'A ...',",
        "  'Tonight ...', 'Something in ...' — NEVER with a verb",
        "- output ONLY the line itself, nothing else — no quotes, no preamble",
        "",
        f"Terrain: stance={stance}; meaning_state={meaning_state}; snr={snr}",
    ]

    if braid_packet:
        af = braid_packet.get("archetype_field") or {}
        wp = braid_packet.get("wisdom_pressure") or {}
        tp = braid_packet.get("traversal_physics") or {}
        traj = braid_packet.get("trajectory") or {}
        sl = ((braid_packet.get("slice") or {}).get("narrowing")) or {}
        eps = (wp.get("epsilon_gate") or {})
        dominant = af.get("dominant") or {}
        trust_d1 = ((traj.get("tick_scale") or {}).get("trust") or {}).get("d1")
        vg = braid_packet.get("voice_guidance") or {}

        lines += [
            f"Dominant working prior: '{dominant.get('fable', 'none')}' — "
            f"{dominant.get('moral', '')}",
            f"Polarity masses: wisdom={af.get('wisdom_mass', 0)}, "
            f"caution={af.get('caution_mass', 0)}",
            f"Route advisory: {tp.get('route_advisory', 'unknown')}",
            f"Jerk flags: {traj.get('jerk_flags') or 'none'}",
            f"Trust velocity (d1): {trust_d1}",
            f"Caution-expression gate fired: {bool(eps.get('fired'))} "
            f"({eps.get('reason', 'n/a')})",
        ]
        if eps.get("fired"):
            lines.append(
                "Register guidance: the caution gate is OPEN — the line may carry an"
                " apophatic shading (what the moment is not, what it cannot hold),"
                " still observational, still wisdom-toned."
            )
        else:
            lines.append(
                "Register guidance: the caution gate is CLOSED — express naturally"
                " and kataphatically: what is, and what it serves."
            )
        if sl.get("narrowed_to"):
            lines.append(f"The slice narrowed to: {sl['narrowed_to']}")
        if sl.get("renarrow_triggers"):
            lines.append(
                "The field re-narrows only when: " + "; ".join(sl["renarrow_triggers"][:4])
            )
        seeds = vg.get("snippet_seeds") or []
        if seeds:
            lines.append("Observational seeds (inspiration, not quotation): "
                         + " | ".join(str(s) for s in seeds[:3]))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM seam (ψ_j — bounded IO, injectable for selftest).
# ---------------------------------------------------------------------------

def _run_claude(prompt: str, model: str, timeout_s: int = LLM_TIMEOUT_S) -> str:
    """Headless `claude -p` call. Raises on failure/timeout (caller absorbs)."""
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--max-turns", "1"],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _select_fallback(disposition: dict[str, Any], epsilon_fired: bool) -> tuple[str, str]:
    """Gate-aware template fallback selection (AMD-1 §4.1).

    Both candidates are ENGINE-CANNED strings (the honest degraded path —
    SPEC names oneWayInjection; the amendment routes the gate state into
    the selection): gate fired → the engine's apophatic `caution` line;
    gate closed → the engine's `oneWayInjection`. Returns (text, template_name).
    """
    disp = disposition.get("disposition") or {}
    if epsilon_fired and disp.get("caution"):
        return str(disp["caution"]), "caution"
    return str(disp.get("oneWayInjection", "")), "one_way_injection"


def propose_voice(
    disposition: dict[str, Any],
    braid_packet: Optional[dict[str, Any]],
    *,
    model: Optional[str] = None,
    kill_switch: Optional[str] = None,
    runner: Callable[[str, str], str] = _run_claude,
) -> dict[str, Any]:
    """Full α/ψ/ρ cycle: propose (LLM or skip) → validate → admit or fall back.

    Deterministic apart from the injectable `runner` seam. Never raises:
    every failure path lands on the template fallback with an honest reason.
    """
    model = model or os.environ.get("HARMONY_VOICE_MODEL", DEFAULT_MODEL)
    kill = (kill_switch if kill_switch is not None
            else os.environ.get("HARMONY_VOICE", "")).strip().lower()

    wp = (braid_packet or {}).get("wisdom_pressure") or {}
    epsilon_fired = bool((wp.get("epsilon_gate") or {}).get("fired"))
    braid_tic = (braid_packet or {}).get("tic")

    started = time.monotonic()
    voice_source = "template_fallback"
    ambient: Optional[str] = None
    validators_passed = False
    fallback_reason: Optional[str] = None
    used_model: Optional[str] = None
    fallback_template: Optional[str] = None

    if kill == "off":
        fallback_reason = "kill_switch:HARMONY_VOICE=off"
    else:
        try:
            raw = runner(build_prompt(disposition, braid_packet), model)
            candidate = raw.strip().strip('"').strip()
            ok, reason = validate_voice(candidate)
            if ok:
                ambient = candidate
                voice_source = "llm"
                validators_passed = True
                used_model = model
            else:
                fallback_reason = f"validation_failed:{reason}"
        except subprocess.TimeoutExpired as exc:
            fallback_reason = f"llm_timeout_{LLM_TIMEOUT_S}s"
            # canary-docket t673 (b): the timeout's partial output was DISCARDED,
            # leaving the 677-683 seven-tic fallback streak with no diagnosable
            # residue. Emit it to stderr — the invoke wrapper captures stderr to
            # a per-tic file (audit-logs/harmony/stderr-tic-N.log).
            for _stream, _payload in (("stdout", exc.stdout), ("stderr", exc.stderr)):
                if _payload:
                    _text = _payload if isinstance(_payload, str) else _payload.decode("utf-8", "replace")
                    print(f"DIAG harmony-voice timeout[{_stream}] model={model}: "
                          f"{_text.strip()[:400]}", file=sys.stderr)
            if not (exc.stdout or exc.stderr):
                print(f"DIAG harmony-voice timeout: NO partial output after {LLM_TIMEOUT_S}s "
                      f"(model={model}) — the CLI hung before emitting anything",
                      file=sys.stderr)
        except FileNotFoundError:
            fallback_reason = "claude_cli_not_found"
        except Exception as exc:
            fallback_reason = f"llm_error:{str(exc)[:160]}"

    if ambient is None:
        ambient, fallback_template = _select_fallback(disposition, epsilon_fired)

    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "ambient_voice": ambient,
        "voice_source": voice_source,
        "model": used_model,
        "duration_ms": duration_ms,
        "validators_passed": validators_passed,
        "fallback_reason": fallback_reason,
        "non_citable": True,
        # AMD-1 §4.2 — naming the α/ψ/ρ split in the receipt:
        "proposer": "bounded_morphism_proposer",
        "admitted_by": "validators_v1",
        "epsilon_gate_fired": epsilon_fired,
        "braid_tic": braid_tic,
        "fallback_template": fallback_template,
    }


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def load_braid_packet() -> Optional[dict[str, Any]]:
    """Fail-soft braid packet loader (pointer → packet); None on any failure."""
    try:
        pointer = json.loads((BRAID_DIR / "current-pointer.json").read_text())
        rel = pointer.get("braid_packet_path")
        if not rel:
            return None
        pkt = json.loads((REPO_ROOT / rel).read_text())
        if not isinstance(pkt, dict) or pkt.get("type") != "lattice.braid.tic":
            return None
        return pkt
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--disposition", help="path to disposition-tic-N.json (required unless --selftest)")
    ap.add_argument("--braid", help="explicit braid packet path (default: braid current-pointer)")
    ap.add_argument("--selftest", action="store_true", help="run the hermetic selftest and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if not args.disposition:
        print("ERR harmony-voice: --disposition required", file=sys.stderr)
        return 1
    disp_path = pathlib.Path(args.disposition)
    try:
        disposition = json.loads(disp_path.read_text())
    except Exception as exc:
        print(f"ERR harmony-voice: cannot read disposition ({exc})", file=sys.stderr)
        return 1

    braid_packet: Optional[dict[str, Any]] = None
    if args.braid:
        try:
            braid_packet = json.loads(pathlib.Path(args.braid).read_text())
        except Exception:
            braid_packet = None
    else:
        braid_packet = load_braid_packet()

    voice = propose_voice(disposition, braid_packet)

    # Additive write INTO the disposition (harmony surface only).
    try:
        disposition["voice"] = voice
        disp_path.write_text(json.dumps(disposition, indent=2))
    except Exception as exc:
        print(f"WARN harmony-voice: disposition writeback failed ({exc})", file=sys.stderr)

    print(json.dumps(voice, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Selftest (deterministic; the LLM seam is mocked — zero network IO).
# ---------------------------------------------------------------------------

def _selftest() -> int:
    checks: list[tuple[str, bool]] = []

    fixture_disposition = {
        "meaningState": "preserved",
        "acousticSignature": {"snr": 0.58},
        "disposition": {
            "stance": "carry-forward-with-light-touch",
            "caution": "Carry the context forward without inflating certainty.",
            "oneWayInjection": "STANCE=carry | MEANING_STATE=preserved | SNR=0.58 | orientation only.",
        },
    }
    fixture_braid_fired = {
        "type": "lattice.braid.tic", "tic": 570,
        "archetype_field": {"wisdom_mass": 0.0, "caution_mass": 1.0,
                            "dominant": {"fable": "The Boy Who Cried Wolf", "moral": "…"}},
        "wisdom_pressure": {"epsilon_gate": {"fired": True, "reason": "caution > wisdom"}},
        "traversal_physics": {"route_advisory": "near_ponr"},
        "trajectory": {"jerk_flags": [], "tick_scale": {"trust": {"d1": 0.0002}}},
        "slice": {"narrowing": {"narrowed_to": "tic 570 field",
                                "renarrow_triggers": ["next heartbeat tic"]}},
        "voice_guidance": {"snippet_seeds": ["the grade ahead reads near_ponr"]},
    }
    fixture_braid_calm = {
        "type": "lattice.braid.tic", "tic": 570,
        "archetype_field": {"wisdom_mass": 0.9, "caution_mass": 0.1,
                            "dominant": {"fable": "The Tortoise and the Hare", "moral": "…"}},
        "wisdom_pressure": {"epsilon_gate": {"fired": False, "reason": "wisdom > caution"}},
        "traversal_physics": {"route_advisory": "cheap"},
        "trajectory": {"jerk_flags": [], "tick_scale": {"trust": {"d1": 0.0001}}},
    }

    # [1] validator rejections — one per gate
    cases = [
        ("imperative_whole_word", "The field must settle before the next move."),
        ("imperative_dont", "Don't read the quiet as absence."),
        ("leading_verb_command", "Hold the line while the terrain settles."),
        ("first_person_plan", "I will carry this forward at the next tic."),
        ("governance_id", "The queue holds cpr_braid_wiring for later."),
        ("doctrine_citation", "As CLAUDE.md notes, the terrain is calm."),
        ("center_naming", "Everything orbits the held-open center tonight."),
        ("multi_line", "A quiet field.\nA long climb."),
        ("too_long", "x" * 241),
        ("empty", "   "),
    ]
    for name, text in cases:
        ok, reason = validate_voice(text)
        checks.append((f"reject_{name}", not ok and reason is not None))

    # [2] valid observational line admits
    ok, reason = validate_voice(
        "The terrain sits high tonight; an old fable about spent alarms hangs in the air, and the grade ahead is steep."
    )
    checks.append(("admit_valid_observational_line", ok and reason is None))

    # [3] kill switch → template fallback with honest reason (no runner call)
    def _explodes(prompt: str, model: str) -> str:
        raise AssertionError("runner called despite kill switch")
    v = propose_voice(fixture_disposition, fixture_braid_fired,
                      kill_switch="off", runner=_explodes)
    checks.append(("kill_switch_skips_llm",
                   v["voice_source"] == "template_fallback"
                   and v["fallback_reason"] == "kill_switch:HARMONY_VOICE=off"))

    # [4] gate-aware fallback selection (AMD-1 §4.1)
    checks.append(("fallback_caution_template_when_gate_fired",
                   v["fallback_template"] == "caution"
                   and v["ambient_voice"] == fixture_disposition["disposition"]["caution"]))
    v_calm = propose_voice(fixture_disposition, fixture_braid_calm,
                           kill_switch="off", runner=_explodes)
    checks.append(("fallback_one_way_injection_when_gate_closed",
                   v_calm["fallback_template"] == "one_way_injection"))

    # [5] mocked LLM success path
    good_line = "A long climb shows in the numbers tonight, and the field carries an old fable about alarms spent too early."
    v_ok = propose_voice(fixture_disposition, fixture_braid_fired,
                         kill_switch="", model="sonnet",
                         runner=lambda p, m: good_line)
    checks.append(("llm_valid_line_admitted",
                   v_ok["voice_source"] == "llm" and v_ok["validators_passed"]
                   and v_ok["ambient_voice"] == good_line and v_ok["model"] == "sonnet"))

    # [6] mocked LLM imperative output → rejected → template fallback
    v_bad = propose_voice(fixture_disposition, fixture_braid_fired,
                          kill_switch="", runner=lambda p, m: "You must slow down now.")
    checks.append(("llm_invalid_line_falls_back",
                   v_bad["voice_source"] == "template_fallback"
                   and str(v_bad["fallback_reason"]).startswith("validation_failed:")))

    # [7] mocked LLM failure (exception) → honest fallback
    def _fails(prompt: str, model: str) -> str:
        raise RuntimeError("simulated transport failure")
    v_err = propose_voice(fixture_disposition, fixture_braid_fired,
                          kill_switch="", runner=_fails)
    checks.append(("llm_error_falls_back_honestly",
                   v_err["voice_source"] == "template_fallback"
                   and str(v_err["fallback_reason"]).startswith("llm_error:")))

    # [7b] TimeoutExpired (with partial output) → honest fallback + no raise;
    # the diagnostic print is stderr-side (captured per-tic by the wrapper) and
    # must never break the propose cycle. (canary-docket t673 (b))
    def _times_out(prompt: str, model: str) -> str:
        raise subprocess.TimeoutExpired(cmd=["claude", "-p"], timeout=LLM_TIMEOUT_S,
                                        output="partial line before hang",
                                        stderr="transport stalled")
    v_to = propose_voice(fixture_disposition, fixture_braid_fired,
                         kill_switch="", runner=_times_out)
    checks.append(("llm_timeout_falls_back_honestly",
                   v_to["voice_source"] == "template_fallback"
                   and v_to["fallback_reason"] == f"llm_timeout_{LLM_TIMEOUT_S}s"))
    def _times_out_silent(prompt: str, model: str) -> str:
        raise subprocess.TimeoutExpired(cmd=["claude", "-p"], timeout=LLM_TIMEOUT_S)
    v_tos = propose_voice(fixture_disposition, fixture_braid_fired,
                          kill_switch="", runner=_times_out_silent)
    checks.append(("llm_timeout_no_partial_output_falls_back",
                   v_tos["voice_source"] == "template_fallback"
                   and v_tos["fallback_reason"] == f"llm_timeout_{LLM_TIMEOUT_S}s"))

    # [8] receipt shape (ρ_j) — required keys + AMD-1 naming, always
    required = {"ambient_voice", "voice_source", "model", "duration_ms",
                "validators_passed", "fallback_reason", "non_citable",
                "proposer", "admitted_by"}
    checks.append(("receipt_schema_complete_all_paths",
                   all(required <= set(x.keys()) for x in (v, v_calm, v_ok, v_bad, v_err))))
    checks.append(("non_citable_always_true",
                   all(x["non_citable"] is True for x in (v, v_calm, v_ok, v_bad, v_err))))
    checks.append(("proposer_admitted_by_named",
                   all(x["proposer"] == "bounded_morphism_proposer"
                       and x["admitted_by"] == "validators_v1"
                       for x in (v, v_calm, v_ok, v_bad, v_err))))

    # [9] prompt carries slice grounding + gate state (AMD-2 §5, AMD-1 §4.1)
    prompt = build_prompt(fixture_disposition, fixture_braid_fired)
    checks.append(("prompt_carries_slice_narrowing",
                   "narrowed to: tic 570 field" in prompt
                   and "next heartbeat tic" in prompt))
    checks.append(("prompt_carries_gate_state_apophatic",
                   "gate is OPEN" in prompt and "apophatic" in prompt))
    prompt_calm = build_prompt(fixture_disposition, fixture_braid_calm)
    checks.append(("prompt_gate_closed_natural_register",
                   "gate is CLOSED" in prompt_calm and "kataphatically" in prompt_calm))

    # [10] no-braid path still proposes (disposition-only prompt, honest nulls)
    v_nob = propose_voice(fixture_disposition, None, kill_switch="",
                          runner=lambda p, m: good_line)
    checks.append(("no_braid_packet_path_works",
                   v_nob["voice_source"] == "llm" and v_nob["braid_tic"] is None
                   and v_nob["epsilon_gate_fired"] is False))

    passed = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 74)
    print(f"RESULT: {passed}/{len(checks)} checks passed — {'OK' if passed == len(checks) else 'FAIL'}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
