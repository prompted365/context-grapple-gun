"""proof_horizon — the comparator over the PROOF-HORIZON LADDER (the horizon axis).

RULED: /review 769 (in-tic Architect-ratified question set) signed the HORIZON
QUIVER build set H1-H4 staged-lock. This module is the ENGINE half of H1, the
load-bearing node. Staged decomposition:
audit-logs/governance/harpoon-office/staging/horizon-quiver-admission-and-dag-tic768.md
section 3 row H1 (as admitted at tic 768: 11,432 B, sha256-16 0fe23c722fe3233b)
and section 6, the /review 769 adjudication appended mid-build (as adjudicated:
12,923 B, sha256-16 ab69feb78ed4600d — sections 1-5 byte-identical across both).
Reviews-lane row: audit-logs/reviews/2026-09-04.jsonl, review_tic 769,
item "H1-H6 build set".

ENGINE-CONTENT SEPARATION (the whole point). The ladder's VALUES and their ORDER
are CONTENT and live in contracts/proof-horizon-ladder-v1.json, ruled at /review
and amendable there by a data edit. This module carries NO ordering of its own —
not as a constant, not as a fallback, not as a default on read failure. Every
rank it returns is read from that file at call time. Adding, removing, or
re-ordering a horizon is an amendment to the contract file; this predicate does
not change.

WHAT A HORIZON IS. The ladder orders EARLIEST-LAWFUL-OBSERVATION INSTANTS of
claims. A horizon is not a workflow stage, not a quality tier, and not a
confidence level: it is the earliest instant at which a claim of that class
becomes lawfully observable at all. A fact that only becomes observable at rank
N+1 cannot be truthfully asserted by an artifact whose own observation stopped
at rank N, however likely it is to be true. An artifact's LAWFUL HORIZON is the
highest rank whose observation has actually been performed for that artifact and
can be pointed at — a measured property of its evidence, never of the author's
intent or the workflow's nominal stage.

THE CONSUMER THIS IS BUILT FOR (NOT BUILT HERE). A receipt claim typed ABOVE its
artifact's lawful horizon — claim rank > artifact rank — is the refusal target of
H2, the receipt-intake horizon check. H2 is UNBUILT. This module answers the
predicate; it is not an intake boundary and it refuses nothing on anyone's
behalf.

DOES NOT SATISFY (rider carried verbatim from the ruling): "H1 does NOT satisfy
H2 (receipt-intake refusal), H3 (remote-parity close predicate), or H4
(detached-reproduction twin); it types the ladder those consumers will read. No
intake boundary refuses anything as of this increment."

FAIL-CLOSED. A missing or malformed ladder file is a TYPED REFUSAL
(LadderUnavailable, carrying a .code), never a fallback ordering — a comparator
that keeps working without its content has silently become a hardcoded engine,
which is the exact defect engine-content separation exists to prevent. An
off-ladder horizon value is a TYPED REFUSAL (OffLadderHorizon), never a silent
default and never rank 0: absence asserts nothing, and the refusal ROUTES the
value to /review rather than declaring the vocabulary complete.

Typed refusal codes: ladder_file_missing · ladder_file_malformed_json ·
ladder_schema_invalid · off_ladder_horizon.
"""

from __future__ import annotations

import json
from pathlib import Path

_CONTRACT_REL = "../../contracts/proof-horizon-ladder-v1.json"

SCHEMA_VERSION = "proof-horizon-ladder-v1"

GOVERNING = ("contracts/proof-horizon-ladder-v1.json (ruled /review 769; staged "
             "decomposition audit-logs/governance/harpoon-office/staging/"
             "horizon-quiver-admission-and-dag-tic768.md section 3 row H1)")

DOES_NOT_SATISFY = (
    "H1 does NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity close "
    "predicate), or H4 (detached-reproduction twin); it types the ladder those "
    "consumers will read. No intake boundary refuses anything as of this "
    "increment.")


def default_ladder_path() -> Path:
    """The shipped contract file. Resolved from THIS module's location so the
    engine and its content travel together; overridable per call for test
    isolation (a self-locating artifact needs explicit pinning under test)."""
    return (Path(__file__).resolve().parent / _CONTRACT_REL).resolve()


# ---------------------------------------------------------------------------
# Typed refusals — every failure exits through one of these, with a .code
# ---------------------------------------------------------------------------

class ProofHorizonRefusal(Exception):
    """Base: every refusal this module raises carries a typed `code`."""

    code = "proof_horizon_refusal"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class LadderUnavailable(ProofHorizonRefusal):
    """The CONTENT could not be read as a valid ladder. FAIL-CLOSED: no
    ordering is substituted, because a fallback order would make the engine the
    author of the vocabulary it is supposed to be reading."""

    code = "ladder_unavailable"


class OffLadderHorizon(ProofHorizonRefusal):
    """A horizon value that the ruled ladder does not carry. Refused to ROUTE it
    to /review — never to declare the vocabulary complete, never defaulted."""

    code = "off_ladder_horizon"


def _unavailable(code: str, detail: str, path: Path) -> LadderUnavailable:
    return LadderUnavailable(
        f"{detail} Ladder path: {path}. FAIL-CLOSED: no fallback ordering is "
        f"substituted — the horizon vocabulary and its order are CONTENT, ruled "
        f"at /review. Governing artifact: {GOVERNING}",
        code=code)


# ---------------------------------------------------------------------------
# load_ladder — the ONLY place the content enters this module
# ---------------------------------------------------------------------------

def _read_ladder_file(path: Path) -> dict:
    """Read and JSON-parse the ladder file. Isolated so the committed suite can
    substitute a stub and prove the engine's ranks come from HERE and nowhere
    else (the reverted-cure control)."""
    if not path.is_file():
        raise _unavailable(
            "ladder_file_missing",
            "The proof-horizon ladder file is missing or is not a regular file.",
            path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _unavailable(
            "ladder_file_missing",
            f"The proof-horizon ladder file could not be read ({exc}).",
            path) from exc
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise _unavailable(
            "ladder_file_malformed_json",
            f"The proof-horizon ladder file is not parseable JSON ({exc}).",
            path) from exc


def _validate(contract, path: Path) -> tuple:
    """Every documented shape violation is a typed ladder_schema_invalid
    refusal. A ladder that half-loads is not a ladder."""
    def bad(detail):
        return _unavailable("ladder_schema_invalid", detail, path)

    if not isinstance(contract, dict):
        raise bad(f"The ladder contract must be a JSON object, got "
                  f"{type(contract).__name__}.")
    version = contract.get("schema_version")
    if version != SCHEMA_VERSION:
        raise bad(f"The ladder contract declares schema_version {version!r}; "
                  f"this engine reads {SCHEMA_VERSION!r}.")
    rungs = contract.get("ladder")
    if not isinstance(rungs, list) or not rungs:
        raise bad("The ladder contract carries no non-empty `ladder` list.")

    order = []
    for position, rung in enumerate(rungs):
        if not isinstance(rung, dict):
            raise bad(f"Ladder entry at position {position} is not an object.")
        name = rung.get("horizon")
        if not isinstance(name, str) or not name:
            raise bad(f"Ladder entry at position {position} carries no "
                      f"non-empty `horizon` name.")
        rank = rung.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise bad(f"Ladder entry {name!r} carries a non-integer `rank` "
                      f"({rank!r}).")
        if rank != position:
            raise bad(f"Ladder entry {name!r} declares rank {rank} at list "
                      f"position {position}; ranks must be contiguous from 0 in "
                      f"list order — a gap or a re-sort silently changes the "
                      f"order the comparator reads.")
        if name in order:
            raise bad(f"Ladder entry {name!r} is declared more than once; a "
                      f"horizon name resolves to exactly one rank.")
        order.append(name)
    return tuple(order)


def load_ladder(path=None) -> dict:
    """Read the ruled ladder from its CONTENT file and return it validated.

    Returns a dict:
      path      — the resolved path actually read (evidence of the source)
      order     — tuple of horizon names, earliest-lawful-observation first
      ranks     — {horizon name: rank}
      contract  — the raw parsed contract

    Raises LadderUnavailable (typed, with .code) if the file is missing,
    unparseable, or not a valid ladder. There is no fallback ordering.
    """
    resolved = Path(path).resolve() if path is not None else default_ladder_path()
    contract = _read_ladder_file(resolved)
    order = _validate(contract, resolved)
    return {
        "path": resolved,
        "order": order,
        "ranks": {name: rank for rank, name in enumerate(order)},
        "contract": contract,
    }


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------

def horizon_rank(name, path=None) -> int:
    """The rank of `name` AS DECLARED IN THE LADDER FILE.

    Raises OffLadderHorizon (typed) on any value the ruled ladder does not
    carry — including None and non-strings. Absence asserts nothing and is NOT
    silently rank 0.
    """
    ladder = load_ladder(path=path)
    ranks = ladder["ranks"]
    if not isinstance(name, str) or name not in ranks:
        raise OffLadderHorizon(
            f"{name!r} is not a ruled proof horizon. Ruled ladder (earliest "
            f"lawful observation first): {list(ladder['order'])}. MINTING "
            f"AUTHORITY: /review — take the horizon to /review; do not coin it "
            f"at the call site. Governing artifact: {GOVERNING}")
    return ranks[name]


def claim_within_horizon(claim_horizon, artifact_horizon, path=None) -> bool:
    """True iff a claim typed at `claim_horizon` is lawful on an artifact whose
    lawful horizon is `artifact_horizon` — that is, iff
    rank(claim) <= rank(artifact).

    False is the OVER-CLAIM case: the artifact's own observation stopped earlier
    than the claim it carries. This function REPORTS that; it refuses nothing
    and blocks nothing. The intake boundary that turns a False into a typed
    refusal is H2, and H2 is unbuilt.

    Raises OffLadderHorizon (typed) if either value is off-ladder.
    """
    ladder = load_ladder(path=path)
    ranks = ladder["ranks"]
    for label, value in (("claim_horizon", claim_horizon),
                         ("artifact_horizon", artifact_horizon)):
        if not isinstance(value, str) or value not in ranks:
            raise OffLadderHorizon(
                f"{label}={value!r} is not a ruled proof horizon. Ruled ladder "
                f"(earliest lawful observation first): {list(ladder['order'])}. "
                f"MINTING AUTHORITY: /review — take the horizon to /review; do "
                f"not coin it at the call site. Governing artifact: {GOVERNING}")
    return ranks[claim_horizon] <= ranks[artifact_horizon]
