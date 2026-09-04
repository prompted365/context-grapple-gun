"""receipt_horizon_guard — the RECEIPT-INTAKE horizon check (H2 of THE HORIZON QUIVER).

RULED: /review 769 (in-tic Architect-ratified question set) signed the HORIZON
QUIVER build set H1-H4 staged-lock; the Architect's word at tic 769 ruled
"Dispatch H2 || H3 || H4 at 770". Staged decomposition:
audit-logs/governance/harpoon-office/staging/horizon-quiver-admission-and-dag-tic768.md
section 3 row H2 (as adjudicated: 12,923 B, sha256-16 ab69feb78ed4600d), verbatim:

    "Receipt-intake horizon check: a receipt claim typed ABOVE its artifact's
     lawful horizon REFUSES with a typed error (same physics locus class as the
     off-enum + undeclared-field guards -- whose first live fires this very tic
     were lawful refusals) | H1 | the receipt-intake boundary + tests (disjoint
     from H3/H4) | signed wave"

Gate evidence: H1's cable receipt
audit-logs/governance/harpoon-office/cable-receipts/H1-proof-horizon-ladder-tic769.json
(receipt id 91cf9b14ba17b8e9) -- "H2 || H3 || H4 tension only after H1's cable
receipt lands." It landed; this is H1's FIRST consumer wiring.

WHAT THIS GUARD IS. A receipt is an artifact that makes CLAIMS. This guard reads
the horizon a receipt types its claims at, reads the horizon that receipt's own
evidence attests, and REFUSES the receipt's admission when the first outranks the
second. That is the t767 over-claimed-verify scar made machine-checkable: a
commit message over-claiming its own verify, a push read as retrieval, a
fixture-green read as live-green.

ENGINE-CONTENT SEPARATION IS INHERITED, NOT RE-IMPLEMENTED. This module carries
NO ordering and NO horizon vocabulary of its own. Every rank it compares comes
from H1's engine (lib/proof_horizon.py) reading H1's content
(contracts/proof-horizon-ladder-v1.json) at call time. Amending the ladder is a
data edit under a /review verdict; this guard does not change.

THE RECEIPT'S DECLARED BLOCK. A receipt opts in by carrying:

    "proof_horizon": {
        "claim_horizon": "<a ruled horizon>",
        "artifact_lawful_horizon": "<a ruled horizon>"
    }

Both key names are H1's OWN vocabulary (the contract's `artifact_lawful_horizon`
field and the engine's `claim_within_horizon(claim_horizon, artifact_horizon)`
signature). NO new term is minted here -- naming law, and the sibling estate's
vocabulary stays excluded (staging section 2 row 16, verdict EXCLUDED).

ABSENCE IS NOT RANK 0 (H1 contract, `absence`). A receipt carrying no
`proof_horizon` block, or a block with no `claim_horizon`, is UNGUARDED -- not
lawful-by-default and not rank 0. Absence asserts nothing, so there is nothing to
refuse. This mirrors classify_enum_value()'s "unguarded" verdict exactly: a field
with no governing contract is not a violation.

FAIL-CLOSED IS SCOPED TO THE JUDGEABLE CASE. If a receipt ASSERTS a claim_horizon
and the guard cannot judge it -- the ladder is missing/malformed, the engine is
unavailable, or the receipt attests no artifact horizon -- the receipt is
REFUSED, never admitted unchecked. Admitting an unverifiable claim is exactly the
laundering this guard exists to stop. But a receipt asserting NOTHING never
consults the ladder, so this guard introduces ZERO new coupling for the corpus
that does not opt in (measured at tic 770: 159 cable receipts, 0 carrying any
horizon key).

TYPED REFUSAL CODES (the same reason-dict shape as the off-enum and
undeclared-field guards -- code / fields / value / message):
  receipt_horizon_over_claim          -- THE ruled target: rank(claim) > rank(artifact)
  receipt_horizon_unattested          -- a claim with no artifact_lawful_horizon to measure it against
  receipt_horizon_off_ladder          -- a horizon value the ruled ladder does not carry (routes to /review)
  receipt_horizon_ladder_unavailable  -- a claim the guard cannot judge (fail-closed)
  receipt_horizon_malformed_block     -- `proof_horizon` present but not an object

DOES NOT SATISFY (rider carried verbatim from the ruling, H1's receipt): "H1 does
NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity close predicate), or
H4 (detached-reproduction twin); it types the ladder those consumers will read.
No intake boundary refuses anything as of this increment."
That rider describes H1. H2 -- this module -- satisfies the FIRST clause only:
an intake boundary now refuses over-claims. H2 does NOT satisfy H3 or H4, and it
does NOT MEASURE any artifact's lawful horizon: it reads the horizon the receipt
ITSELF attests and enforces internal consistency against the claim. Independently
measuring an artifact's true lawful horizon remains unbuilt -- H3 (remote parity)
and H4 (detached reproduction) are the instruments that would measure the upper
rungs, and both are outside this increment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_LIB_DIR = Path(os.path.abspath(__file__)).resolve().parent

BLOCK_KEY = "proof_horizon"
CLAIM_KEY = "claim_horizon"
ARTIFACT_KEY = "artifact_lawful_horizon"

GOVERNING = (
    "contracts/proof-horizon-ladder-v1.json via lib/proof_horizon.py (ruled "
    "/review 769; staged decomposition audit-logs/governance/harpoon-office/"
    "staging/horizon-quiver-admission-and-dag-tic768.md section 3 row H2)")

MINTING_AUTHORITY = (
    "/review -- take the horizon to /review; do not coin it at the call site.")

DOES_NOT_SATISFY = (
    "H1 does NOT satisfy H2 (receipt-intake refusal), H3 (remote-parity close "
    "predicate), or H4 (detached-reproduction twin); it types the ladder those "
    "consumers will read. No intake boundary refuses anything as of this "
    "increment.")

# What H2 itself does NOT satisfy -- carried so no reader mistakes this module
# for the measurement instruments that are still unbuilt.
H2_DOES_NOT_SATISFY = (
    "H2 refuses a receipt whose claim_horizon outranks the artifact_lawful_horizon "
    "THE RECEIPT ITSELF ATTESTS. H2 does NOT independently measure any artifact's "
    "lawful horizon, does NOT satisfy H3 (remote-parity close predicate) or H4 "
    "(detached-reproduction twin), and refuses nothing on any surface other than "
    "the receipt-intake boundary it is wired into.")


def _engine():
    """Load H1's comparator. Returns the module, or None if it cannot be loaded.

    NOT fail-soft in effect: a caller that cannot load the engine must treat an
    ASSERTED claim as unjudgeable and refuse it (see classify_receipt_horizon).
    Returning None rather than raising keeps the decision at the boundary, where
    the fail-closed scope is declared, instead of hiding it in an import.
    """
    if str(_LIB_DIR) not in sys.path:
        sys.path.insert(0, str(_LIB_DIR))
    try:
        import proof_horizon  # noqa: PLC0415  (deliberately lazy)
        return proof_horizon
    except Exception:
        return None


def _reason(code: str, message: str, value=None) -> dict:
    """The reason-dict shape the sibling guards emit (code / fields / value /
    message), so one reporting path can render every refusal in this family."""
    return {
        "code": code,
        "fields": [BLOCK_KEY],
        "value": value,
        "message": message,
    }


def classify_receipt_horizon(artifact, ladder_path=None) -> dict:
    """Classify a receipt artifact's horizon block at the intake boundary.

    Returns a verdict dict:
      verdict   -- "unguarded" | "lawful" | "refused"
      code      -- None when not refused; a typed refusal code otherwise
      claim     -- the claim_horizon read from the receipt (or None)
      attested  -- the artifact_lawful_horizon read from the receipt (or None)
      reason    -- None, or the reason dict (code/fields/value/message)

    NEVER raises for a receipt-shaped input: the boundary decides, not the
    import. Absence is "unguarded" and is NOT rank 0.
    """
    def refused(code, message, value=None, claim=None, attested=None):
        return {"verdict": "refused", "code": code, "claim": claim,
                "attested": attested, "reason": _reason(code, message, value)}

    if not isinstance(artifact, dict) or BLOCK_KEY not in artifact:
        # Absence asserts nothing (H1 contract, `absence`). Not rank 0.
        return {"verdict": "unguarded", "code": None, "claim": None,
                "attested": None, "reason": None}

    block = artifact.get(BLOCK_KEY)
    if not isinstance(block, dict):
        return refused(
            "receipt_horizon_malformed_block",
            f"{BLOCK_KEY!r} is present but is not an object (got "
            f"{type(block).__name__}). A horizon declaration that cannot be read "
            f"is not a declaration; the receipt is refused rather than admitted "
            f"unchecked. Governing artifact: {GOVERNING}",
            value=block)

    claim = block.get(CLAIM_KEY)
    attested = block.get(ARTIFACT_KEY)

    if claim is None:
        # Opted-in block asserting no claim: nothing to refuse. Still unguarded.
        return {"verdict": "unguarded", "code": None, "claim": None,
                "attested": attested, "reason": None}

    if attested is None:
        return refused(
            "receipt_horizon_unattested",
            f"the receipt types a claim at {claim!r} but attests no "
            f"{ARTIFACT_KEY!r}. A claim horizon with nothing to measure it "
            f"against cannot be judged, and an unjudgeable claim is refused, "
            f"never admitted unchecked. Declare the highest horizon this "
            f"artifact's own evidence actually reached. Governing artifact: "
            f"{GOVERNING}",
            value=claim, claim=claim, attested=None)

    engine = _engine()
    if engine is None:
        return refused(
            "receipt_horizon_ladder_unavailable",
            f"the receipt types a claim at {claim!r} but the proof-horizon "
            f"comparator could not be loaded, so the claim cannot be judged. "
            f"FAIL-CLOSED: an unverifiable claim is refused, never admitted with "
            f"a substituted ordering -- a guard that keeps passing without its "
            f"content has silently become a rubber stamp. Governing artifact: "
            f"{GOVERNING}",
            value=claim, claim=claim, attested=attested)

    try:
        within = engine.claim_within_horizon(claim, attested, path=ladder_path)
    except engine.OffLadderHorizon as exc:
        return refused(
            "receipt_horizon_off_ladder",
            f"{exc}. MINTING AUTHORITY: {MINTING_AUTHORITY}",
            value=[claim, attested], claim=claim, attested=attested)
    except engine.ProofHorizonRefusal as exc:
        return refused(
            "receipt_horizon_ladder_unavailable",
            f"the receipt types a claim at {claim!r} but the ruled ladder could "
            f"not be read ({getattr(exc, 'code', 'proof_horizon_refusal')}): "
            f"{exc} FAIL-CLOSED: the claim is refused, never admitted unchecked.",
            value=claim, claim=claim, attested=attested)

    if not within:
        return refused(
            "receipt_horizon_over_claim",
            f"the receipt types a claim at {claim!r} but its own evidence "
            f"attests only {attested!r} -- the claim OUTRANKS the artifact's "
            f"lawful horizon. A fact that becomes observable only at a later "
            f"horizon cannot be truthfully asserted by an artifact whose own "
            f"observation stopped earlier, however likely it is to be true. "
            f"Either perform the observation the claim names, or type the claim "
            f"at {attested!r}. Governing artifact: {GOVERNING}",
            value=claim, claim=claim, attested=attested)

    return {"verdict": "lawful", "code": None, "claim": claim,
            "attested": attested, "reason": None}
