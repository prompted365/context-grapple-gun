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
"""

from __future__ import annotations

import json
from pathlib import Path

_CONTRACT_REL = "../../contracts/confidence-tier-enum-v1.json"

GOVERNING = ("contracts/confidence-tier-enum-v1.json (ratified /review 708; "
             "ruling rows audit-logs/reviews/2026-08-12.jsonl "
             "decision_id off-enum-ruling-1..4)")


def _load_contract() -> dict:
    path = (Path(__file__).resolve().parent / _CONTRACT_REL).resolve()
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


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
    """
    if value is None:
        return "lawful"
    if not isinstance(value, str):
        return "off_enum"
    if value in TIER_ENUM:
        return "lawful"
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
