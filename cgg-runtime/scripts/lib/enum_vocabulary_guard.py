#!/usr/bin/env python3
"""enum_vocabulary_guard — the ONE contract-loader + classify + refusal-message
triple that every contract-guarded vocabulary writer consumes.

WHY THIS EXISTS (OM-W10-4, handed up by the wave-10 build citizen; admitted as
the wave-11 build sibling in B2-wave-11-SIGNED-tic773.json, self-sha
3c46db86c0580d4e over STAGED c456ba46492885c5). Row
`bk-off-enum-drift-field-generic-writer-topology`.

The row's whole finding is that the pending_class drift axis is **MULTIPLE
WRITERS WITH NO SHARED CONTRACT** (contracts/pending-class-enum-v1.json,
`writer_topology`). Waves 5 and 10 closed the behavioural half by landing the
same guard at all three writers — queue-lifecycle-writeback.py (tic 767),
cpr-extract.py and queue_event_writer.py (tic 772). But the guard was landed
three TIMES: three loaders, three classifiers, three refusal-message builders,
each a faithful copy. "One contract, N writers" was true by CONVENTION —
maintained by whoever remembered to edit all three — which is the same shape as
the defect one rung up: a vocabulary that depends on producer restraint is not
a vocabulary, it is a habit.

This module makes it STRUCTURAL. The three writers now share one implementation
of the triple, so a change to the guard's engine reaches every writer by
construction rather than by diligence. The cross-writer test asserts the shared
module OBJECT identity, not a resemblance between three copies.

WHAT MOVED AND WHAT DID NOT — the boundary is load-bearing:
  MOVED  (engine)  — the loader, the classify predicate, the refusal text.
  STAYED (content) — every enum's VALUES, its contract file, its accretion
                     posture and its minting authority. Engine-content
                     separation is a federation KI, and this module is the
                     engine side of it: it holds NO vocabulary, names NO field,
                     and reads NO contract path of its own. Callers pass their
                     own contract dir + filename + enum. Extending a vocabulary
                     remains a DATA EDIT in contracts/ authorized by a /review
                     verdict.
  STAYED (state)   — each writer keeps its OWN module-level enum/contract
                     bindings, and its public predicate reads them at CALL time.
                     That is deliberate: the existing guard fixtures monkeypatch
                     those module-level bindings to simulate drift (shrink the
                     enum, unbind a field), and a lib that cached its own copy
                     would silently defeat every one of those controls.

NOT FAIL-SOFT, deliberately (the confidence_tier discipline, inherited from all
three call sites): a guard surface whose governing contract is missing must
crash LOUDLY at import rather than run half-guarded.

THE EMPTY-STRING ASYMMETRY IS PRESERVED, NOT RESOLVED (F-773-W11-1). The two
guard families disagree today about whether `""` is an absence form:
  cpr-extract.py / queue_event_writer.py — `""` is LAWFUL (absence)
  queue-lifecycle-writeback.py           — `""` is OFF_ENUM (not a member)
`empty_string_is_absence` carries that difference explicitly instead of
silently picking a winner. Unifying it would be a VOCABULARY SEMANTICS change
at a governed write boundary — /review's call, not an extraction's, so this
module preserves both behaviours byte-for-byte and the divergence is handed up
as an owed motion. A DRY cure that quietly re-typed a value at three write
boundaries would be exactly the laundering this row exists to stop.

DOES NOT SATISFY (rider carried verbatim from the wave-11 ruling,
B2-wave-11-SIGNED-tic773.json): "this increment does NOT author a HOLD
generator contract (future work, unruled); does NOT touch the office_map
(standing fence per /review 772 Q5); does NOT re-truth the contract JSON
(seat-owned data surface); does NOT claim the all-rows historical complement
cured"
"""
from __future__ import annotations

import json
from pathlib import Path

LAWFUL = "lawful"
OFF_ENUM = "off_enum"


def load_contract(contracts_dir, filename):
    """Load a vocabulary contract. NOT fail-soft — a missing contract raises.

    `contracts_dir` is the CALLER's resolved contracts directory: this module
    resolves no path of its own, so it can never bind a writer to a contract the
    writer did not name.
    """
    with open(Path(contracts_dir) / filename, encoding="utf-8") as fh:
        return json.load(fh)


def classify(value, enum, empty_string_is_absence=False):
    """Classify a candidate value against a ratified `enum`.

    Returns LAWFUL for an enum member or a lawful no-value form, OFF_ENUM for
    any other coinage INCLUDING a non-string (a non-string can never be an enum
    member, and admitting one would put an unreadable value on a governed row).

    `empty_string_is_absence` selects the caller's declared absence semantics —
    see the module docstring: the two guard families genuinely disagree, and the
    disagreement is carried, never resolved here.
    """
    if value is None:
        return LAWFUL
    if empty_string_is_absence and value == "":
        return LAWFUL
    if not isinstance(value, str):
        return OFF_ENUM
    return LAWFUL if value in enum else OFF_ENUM


def refusal_message(field, value, enum, contract, contract_filename,
                    locator=None):
    """The typed reject text — the guard's MOST-READ surface.

    Load-bearing per the ruling that landed it: it names the offending value,
    the lawful set, the CONTRACT FILE, and /review as the MINTING AUTHORITY, so
    a caller who hits it learns where the vocabulary lives and who may extend it
    — never just that it failed. Interpolated from the contract, so a data edit
    updates the message too.

    `locator` is appended only when the caller supplies one (the birth writers
    can name the exact block/row; the lifecycle writer reports its violations in
    a structured reasons list that carries the location separately).
    """
    message = (
        f"{value!r} is not a ratified {field} value. Lawful values: "
        f"{sorted(enum)} or absent. Governing artifact: "
        f"contracts/{contract_filename} ({contract['ratified']}). "
        f"MINTING AUTHORITY: {contract['minting_authority']}"
    )
    if locator is not None:
        message += f" Refused at {locator}."
    return message
