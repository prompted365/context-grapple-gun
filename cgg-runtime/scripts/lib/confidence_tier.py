"""confidence_tier vocabulary guard — the /review 708 write-boundary physics.

Ratified at /review 708 (off-enum rulings 1-4, Architect-ratified in-tic):
the confidence_tier field carries a ratified-enum member or is ABSENT; the
vocabulary must not depend on producer restraint (A6-707). CONTENT lives in
contracts/confidence-tier-enum-v1.json (engine-content separation) — extending
the enum is a data edit there, never a rewrite of this predicate.

Two write surfaces consume this module:
  - cogpr-ingest.py (birth): an off-enum candidate value is stripped to ABSENT
    with a typed `tier_refusal` marker on the row + a loud stderr TIER-REFUSAL
    notice — the lesson is never dropped (a row-level reject at a background
    birth surface would be its own coverage drop; guard 10's shape).
  - queue-lifecycle-writeback.py (verdict writeback): INTRODUCTION of an
    off-enum value is refused (rc=2 / validate-row rc=3); unchanged
    carry-forward of a historical off-enum value stays lawful and is disclosed
    (ruling 2 keeps the 31 historical marker rows as-is — the guard must not
    refuse lawful copy-forward).

SHARED-ENGINE MIGRATION (B2 wave 12, OM-W11-4, ruled in
B2-wave-12-SIGNED-tic775.json self-sha b4f2177919d6bc72 over STAGED
cf65b8c68db0dcfe). Row `bk-off-enum-drift-field-generic-writer-topology`.

Wave 11 unified THREE copies of the loader/classify/refusal triple onto
lib/enum_vocabulary_guard.py; this module was the FOURTH copy of the same
pattern, outside that wave's fence (F-773-W11-3). It now consumes the shared
engine, so the guard's engine reaches this writer by CONSTRUCTION rather than by
whoever remembers to edit the fourth copy.

WHAT MOVED AND WHAT DID NOT — the boundary is load-bearing:
  MOVED  (engine)  — the contract READ (enum_vocabulary_guard.load_contract) and
                     the BASE lawful/off_enum decision
                     (enum_vocabulary_guard.classify, empty_string_is_absence
                     =False — the tier family's existing semantics, UNCHANGED).
  STAYED (content) — the FOUR-kind refinement. This family is RICHER than the
                     shared two-kind engine: `class_bleed` and `non_tier_marker`
                     are /review-708 RULED CONTENT read from the contract's
                     `refused_as_tier` sets, and the per-kind refusal DETAIL is
                     this caller's text. Engine-content separation: the engine
                     decides membership, the caller owns its vocabulary's
                     meaning. (The shared refusal_message is deliberately NOT
                     consumed — it interpolates `contract['minting_authority']`,
                     a key this contract does not carry, and its wording is a
                     different ruled text.)
  STAYED (state)   — TIER_ENUM / CONFIDENCE_CLASS_VALUES / NON_TIER_MARKERS /
                     GOVERNING / _CONTRACT remain MODULE-LEVEL, and the public
                     predicates read them at CALL time. A lib-cached copy would
                     defeat any drift control that rebinds them.

THE isinstance(str) GUARD IS LOAD-BEARING, NOT INCIDENTAL: the four-kind
refinement must never run a membership test on a non-string, because an
UNHASHABLE value (list / dict / set) raises TypeError on `in`. The base engine
returns OFF_ENUM for every non-string without hashing it, and the refinement
below re-asserts the isinstance guard before touching either refused_as_tier
set. Pinned by the tic-775 equivalence table.

NOT FAIL-SOFT, deliberately (inherited from both call sites and from the shared
engine): a guard surface whose governing contract is missing must crash LOUDLY
at import rather than run half-guarded. The sibling import below is likewise
unguarded — a missing engine is a crash, never a silent half-guard.

THREE IMPORT FORMS EXIST ON DISK and all three must resolve the engine, which is
why this module puts its OWN directory on sys.path (the house pattern, cf.
lib/cockpit_intent_emit.py, lib/dsn_fragment.py, lib/fragment_receipt.py)
instead of relying on the caller's:
  1. `from confidence_tier import ...`      — queue-lifecycle-writeback.py:172
     (scripts/ AND scripts/lib both on sys.path)
  2. `from lib.confidence_tier import ...`  — cogpr-ingest.py:331
     (only scripts/ on sys.path — a bare sibling import would raise
     ModuleNotFoundError here; measured at tic 775, not assumed)
  3. spec_from_file_location under an ARBITRARY module name —
     test_proof_horizon_ladder_tic769.py:490 (no package context at all)

DOES NOT SATISFY (rider carried verbatim from the wave-12 ruling,
B2-wave-12-SIGNED-tic775.json): "this increment does NOT resolve the tier
family's empty-string semantics (unchanged, empty_string_is_absence=False); does
NOT touch the pending_class writers or their guards; does NOT re-truth any
contract JSON; does NOT touch the office_map (standing fence /review 772 Q5);
does NOT author the HOLD generator contract (OM-W11-3, un-slotted); does NOT
cure the standing collection error (P6)."
"""

from __future__ import annotations

import sys
from pathlib import Path

# The shared enum-guard engine (B2 wave 12, OM-W11-4) — the loader + the base
# classify. Self-inserting this lib dir keeps the ONE module object reachable
# under all three import forms named in the docstring, so every writer that
# guards a contract vocabulary shares a single engine by identity.
_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
import enum_vocabulary_guard  # noqa: E402

_CONTRACT_DIR_REL = "../../contracts"
_CONTRACT_FILENAME = "confidence-tier-enum-v1.json"

GOVERNING = ("contracts/confidence-tier-enum-v1.json (ratified /review 708; "
             "ruling rows audit-logs/reviews/2026-08-12.jsonl "
             "decision_id off-enum-ruling-1..4)")


def _load_contract() -> dict:
    """Read this vocabulary's contract THROUGH THE SHARED ENGINE.

    The engine resolves no path of its own — this caller names its own contracts
    dir and filename, so the shared loader can never bind this writer to a
    contract it did not name.
    """
    return enum_vocabulary_guard.load_contract(
        (_LIB_DIR / _CONTRACT_DIR_REL).resolve(), _CONTRACT_FILENAME)


_CONTRACT = _load_contract()
TIER_ENUM = frozenset(_CONTRACT["enum"].keys())
CONFIDENCE_CLASS_VALUES = frozenset(
    _CONTRACT["refused_as_tier"]["confidence_class_values"])
NON_TIER_MARKERS = frozenset(_CONTRACT["refused_as_tier"]["non_tier_markers"])


def classify_tier_value(value):
    """Classify a candidate confidence_tier value.

    Returns one of:
      "lawful"          — enum member (or None/absent, the lawful no-tier form)
      "class_bleed"     — a confidence_class enum value in the tier field
                          (field-routing defect; ruling 1's seam)
      "non_tier_marker" — an absence/observation marker as a value (ruling 2)
      "off_enum"        — any other coinage

    The BASE lawful/off_enum decision is the shared engine's
    (empty_string_is_absence=False — `""` is NOT an absence form for this
    family, unchanged by the migration). The OFF_ENUM half is then REFINED into
    this family's three ruled refusal kinds from the contract's
    `refused_as_tier` sets. Module-level bindings are read at CALL time.
    """
    base = enum_vocabulary_guard.classify(
        value, TIER_ENUM, empty_string_is_absence=False)
    if base == enum_vocabulary_guard.LAWFUL:
        return "lawful"
    # Refine the engine's OFF_ENUM into the tier family's ruled sub-kinds.
    # The isinstance(str) guard stays AHEAD of both membership tests: an
    # unhashable non-string would raise TypeError on `in` (see module docstring).
    if isinstance(value, str):
        if value in CONFIDENCE_CLASS_VALUES:
            return "class_bleed"
        if value in NON_TIER_MARKERS:
            return "non_tier_marker"
    return "off_enum"


def refusal_message(value, kind) -> str:
    detail = {
        "class_bleed": (f"{value!r} is a lawful confidence_class value in the "
                        f"confidence_tier field — field-routing bleed, not a tier"),
        "non_tier_marker": (f"{value!r} asserts no tier — represent 'no tier "
                            f"asserted' by omitting the field"),
        "off_enum": f"{value!r} is not a ratified confidence_tier",
    }[kind]
    return (f"{detail}. Lawful values: {sorted(TIER_ENUM)} or absent. "
            f"Governing artifact: {GOVERNING}")
