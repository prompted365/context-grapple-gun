#!/usr/bin/env python3
"""boot-injection.py — shared tic-gated boot-injection lane (tic 320).

A lightweight, REUSABLE injection lane that both boot seams read:
  - session-restore.sh   (SessionStart — the interactive orchestrator, ent_homeskillet)
  - subagent-citizen-boot.py (SubagentStart — every recognized citizen)

so a pointer (e.g. the GLOSSARY doctrine-surface navigation frame) can be popped into
boot context for a bounded window of tics, with an auto re-evaluation reminder at a
target tic. This is the ambient-injection complement to the citizen-boot REMINDERS lane
(autonomous_kernel/citizen-boot-reminders-spec.md §3): that lane is per-actor scheduled
obligations; this lane is a broadcast pointer with a tic window.

LOOP-SAFETY (spec §5 — non-negotiable): the RENDER path is READ-ONLY. It mints NO signals
and writes NO governance state — it only reads a registry and prints text. The 200+ signal
runaway class cannot recur through it. Per-boot context bloat is prevented by the calling
hooks' existing dedup-on-unchanged (same rendered text → injected once per session/entity).
The REFRESH verb (below) is a governed WRITE verb — never invoked by either boot seam; it
appends to the registry under the refresh claim-gate and is fail-CLOSED (a silent-0 on a
failed refresh would be the exact vacuous-green shape the gate exists to prevent).

REGISTRY: audit-logs/boot-injections/active.jsonl  (append-only, latest-entry-per-id wins —
terminal-valve discipline). Record schema:
  {
    "injection_id": "<stable id>",          # condition-stable, not timestamp/uuid
    "inject_from_tic": 320,
    "inject_until_tic": 350,                 # inclusive; after this, the injection is dormant
    "reminder_at_tic": 350,                  # at/after this tic, render reminder_text instead
    "audience": "all",                       # "all" | "orchestrator" | "citizens" | ["ent_x", ...]
    "inject_text": "...",                    # the pointer/frame to inject during the window
    "reminder_text": "...",                  # the re-eval reminder at reminder_at_tic
    "status": "active"                       # "active" renders; any non-active state (retired|superseded|closed|...) => never render; missing => active
  }

CLI:
  boot-injection.py render --tic N --audience <orchestrator|citizens|ent_xxx>
      -> prints the concatenated active injection text for that audience at tic N
         (empty output + exit 0 when nothing is due — SILENT-WHEN-EMPTY)

  boot-injection.py refresh --injection-id ID --tic N --refresh-reason "..."
      (--inject-text "..." | --inject-text-file PATH)
      [--claim '{"token": "x.py", "source": "<zone-relative path>", "evidence": "<substr>"}']...
      [--waive-claim '{"token": "x.py", "reason": "..."}']...
      -> appends a refreshed row (latest-per-id wins) carrying the existing WHY receipt
         (refreshed_at_tic + refresh_reason) PLUS a WHAT-verification receipt, under the
         REFRESH CLAIM-GATE (constitution-ledger#refresh-is-inscription-event-vacuous-green-conceals):
         a refresh is itself an inscription event; when it changes what a TOOL is claimed
         to DO, the new claim is verified against the tool's source AT REFRESH TIME —
         the same claim-gate the handoff already has (verify against the real artifact
         before the claim lands). Tool claims = text fragments mentioning *.py / *.sh
         tokens; a token whose fragment-set changed (or is new) owes exactly one --claim
         (evidence substring located in the resolved source at refresh time, source sha256
         computed-at-write) or one --waive-claim (explicit, reasoned, VISIBLE in the
         receipt — surface-don't-hide). A token REMOVED from the text makes no new claim
         and owes nothing. Exit codes: 0 refreshed · 2 usage/target/typo errors
         (registry/id missing, non-active target, claim naming an unchanged token) ·
         3 claim-gate refusal (claim_missing | source_unresolved | evidence_not_in_source)
         — refusal lands BEFORE any side effect; the registry is untouched.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def _zone_root(start: Path, explicit: str = None):
    """Resolve the canonical zone root (where audit-logs/ lives).

    Order: explicit --zone-root (the caller already resolved it) > walk up from
    __file__ (works when running from canonical source) > walk up from cwd (works
    when installed under ~/.claude but fired with cwd=project). The installed copy
    under ~/.claude CANNOT find .ticzone by __file__ walk — callers MUST pass
    --zone-root for the installed path."""
    if explicit:
        ep = Path(explicit)
        if (ep / ".ticzone").is_file():
            return ep
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    return None


def _load_registry(zone_root: Path):
    """Latest-entry-per-id wins (terminal-valve read over the append-only registry)."""
    reg = zone_root / "audit-logs" / "boot-injections" / "active.jsonl"
    byid = {}
    if not reg.is_file():
        return []
    for line in reg.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        iid = r.get("injection_id")
        if iid:
            byid[iid] = r
    return list(byid.values())


def _audience_match(record_audience, who: str) -> bool:
    """who is 'orchestrator', 'citizens', or a concrete 'ent_*' id."""
    if record_audience == "all":
        return True
    if isinstance(record_audience, list):
        return who in record_audience
    if record_audience == who:
        return True
    # citizens-class request matches a concrete ent_* audience only via the list/all forms above;
    # 'orchestrator' and 'citizens' are the two broad lanes.
    return False


def render(zone_root: Path, tic: int, who: str, max_chars: int = 0) -> str:
    # Collect (priority, from_tic, text) so the join is PRIORITY-ordered, not
    # registry-insertion-ordered. Lower priority int = more important (renders
    # first). `priority` is an OPTIONAL record field (default 50); a missing field
    # keeps today's behavior except for the deterministic (priority, from_tic) sort.
    items = []
    for r in _load_registry(zone_root):
        # Render ACTIVE only. A boot-injected pointer is itself a rehydration (a parent-law
        # pointer carried to a citizen's boot); a non-active record injected as if current
        # re-creates downstream staleness — the recursion-trap of the inheritance carrier
        # (No magical inheritance across rungs: boot pointers must resolve top-current).
        # Skip every non-active terminal state (retired | superseded | closed | <anything>),
        # defaulting a missing status to "active" for backward-compat with seed records.
        if r.get("status", "active") != "active":
            continue
        aud = r.get("audience", "all")
        # 'citizens' lane: a record addressed to "all" or "citizens" reaches every citizen;
        # 'orchestrator' lane: "all" or "orchestrator". Concrete ent_* audiences match exactly.
        reachable = (
            _audience_match(aud, who)
            or (who.startswith("ent_") and aud in ("all", "citizens"))
            or (who == "citizens" and aud in ("all", "citizens"))
            or (who == "orchestrator" and aud in ("all", "orchestrator"))
        )
        if not reachable:
            continue
        rem_at = r.get("reminder_at_tic")
        frm = r.get("inject_from_tic", 0)
        until = r.get("inject_until_tic", 10**9)
        txt = ""
        if rem_at is not None and tic >= rem_at:
            txt = (r.get("reminder_text") or r.get("inject_text") or "").strip()
        elif frm <= tic <= until:
            txt = (r.get("inject_text") or "").strip()
        if not txt:
            continue
        try:
            pri = int(r.get("priority", 50))
        except (TypeError, ValueError):
            pri = 50
        items.append((pri, frm, txt, r.get("injection_id") or "?"))

    items.sort(key=lambda t: (t[0], t[1]))

    # No budget -> render all (today's behavior, just priority-ordered).
    if not max_chars:
        return " ".join(t[2] for t in items).strip()

    # Budgeted: accumulate at UNIT boundaries; the lowest-priority pointers seal
    # first. The overflow marker is a PERTINENCE MANIFEST (not a bare count) so a
    # consumer can judge expand-or-not from the marker itself — same standard as the
    # consumer-side apophatic aperture (cgg-ledger#producer-seal-is-a-typed-field-aperture,
    # /review 421). Never cut mid-fragment (unit-safe).
    kept, used, sealed_ids = [], 0, []
    for _pri, _frm, txt, iid in items:
        add = (1 if kept else 0) + len(txt)  # +1 for the join space
        if used + add > max_chars and kept:
            sealed_ids.append(iid)
            continue
        kept.append(txt)
        used += add
    if sealed_ids:
        kept.append(_seal_manifest(sealed_ids))
    return " ".join(kept).strip()


def _seal_manifest(sealed_ids: list) -> str:
    """The boot-injection budget seal as a PERTINENCE MANIFEST, not a bare count
    (cgg-ledger#producer-seal-is-a-typed-field-aperture, /review 421). A producer seal must
    NAME + TYPE its negative space so a consumer can judge expand-or-not from the marker:
    sealed_ids (the injection_id semantic slugs = the PERTINENCE handle, top-N + '+k more')
    + a follow_surface + a read_discipline. Carries NO priority_range — RANK ≠ PERTINENCE:
    what lets a consumer judge expand-or-not is WHAT was sealed (the semantic id), not how the
    producer ranked it. The omitted pointers RETAIN their pertinence; they are budget-BOUNDED,
    not foreclosed — expand if pertinent."""
    n = len(sealed_ids)
    TOP = 8
    shown = sealed_ids[:TOP]
    more = n - len(shown)
    id_str = ", ".join(shown) + (f" +{more} more" if more > 0 else "")
    return (
        f"[BOOT-INJECTION BUDGET — {n} lower-priority pointer(s) bounded by render (not foreclosed): "
        f"{id_str}. EXPAND if pertinent. follow-surface: audit-logs/boot-injections/active.jsonl "
        "(read_discipline: latest-entry-per-id / terminal-valve)]"
    )


# ---------------------------------------------------------------------------
# REFRESH CLAIM-GATE (bk-boot-injection-refresh-claim-gate, admitted /review 624,
# lowered t626, built t630). Doctrine home:
# constitution-ledger#refresh-is-inscription-event-vacuous-green-conceals.
# ---------------------------------------------------------------------------

# A "tool" for claim purposes is an executable script token (*.py / *.sh) —
# the class whose claimed behavior the t621 refresh drifted against source.
_TOOL_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.(?:py|sh)\b")


def _claim_contexts(text: str) -> dict:
    """tool-token -> set of normalized text fragments (sentence-ish) mentioning it.

    The fragment set IS the claim about the tool: if it differs between the old
    and new inject_text, the refresh changed what that tool is claimed to DO."""
    ctx = {}
    for frag in re.split(r"(?<=[.;!?])\s+|\n+", text or ""):
        norm = " ".join(frag.split())
        if not norm:
            continue
        for m in _TOOL_TOKEN_RE.finditer(norm):
            ctx.setdefault(m.group(0), set()).add(norm)
    return ctx


def _changed_tool_claims(old_text: str, new_text: str) -> list:
    """Tokens in the NEW text whose claim fragments are new or changed vs OLD.

    A token present only in the OLD text (removed by the refresh) makes no new
    claim and owes no verification — there is no new assertion to check against
    source. A token with an IDENTICAL fragment set owes nothing either: the
    refresh did not change what that tool is claimed to do."""
    old_ctx = _claim_contexts(old_text)
    new_ctx = _claim_contexts(new_text)
    return sorted(tok for tok, frags in new_ctx.items() if old_ctx.get(tok) != frags)


def _typed(status: str, payload: dict, stream=None) -> None:
    """Structured stdout line (typed + visible)."""
    (stream or sys.stdout).write(json.dumps({"status": status, **payload}) + "\n")


def _refresh(args) -> int:
    zone_root = _zone_root(Path(__file__).resolve().parent, args.zone_root)
    if zone_root is None:
        _typed("refused", {"reason": "zone_unresolved"})
        sys.stderr.write("[boot-injection refresh] REFUSED: zone_unresolved\n")
        return 2
    reg = zone_root / "audit-logs" / "boot-injections" / "active.jsonl"
    if not reg.is_file():
        _typed("refused", {"reason": "registry_missing", "registry": str(reg)})
        sys.stderr.write("[boot-injection refresh] REFUSED: registry_missing\n")
        return 2

    # Exactly one text source (both arms documented: both-given / neither-given refuse).
    if bool(args.inject_text) == bool(args.inject_text_file):
        _typed("refused", {"reason": "inject_text_source_not_exactly_one"})
        sys.stderr.write("[boot-injection refresh] REFUSED: pass exactly one of "
                         "--inject-text / --inject-text-file\n")
        return 2
    new_text = (args.inject_text if args.inject_text
                else Path(args.inject_text_file).read_text(encoding="utf-8")).strip()
    if not new_text:
        _typed("refused", {"reason": "inject_text_empty"})
        sys.stderr.write("[boot-injection refresh] REFUSED: inject_text_empty\n")
        return 2

    byid = {r.get("injection_id"): r for r in _load_registry(zone_root)}
    target = byid.get(args.injection_id)
    if target is None:
        _typed("refused", {"reason": "refresh_target_missing",
                           "injection_id": args.injection_id})
        sys.stderr.write("[boot-injection refresh] REFUSED: refresh_target_missing\n")
        return 2
    if target.get("status", "active") != "active":
        _typed("refused", {"reason": "refresh_target_not_active",
                           "injection_id": args.injection_id,
                           "target_status": target.get("status")})
        sys.stderr.write("[boot-injection refresh] REFUSED: refresh_target_not_active\n")
        return 2

    old_text = (target.get("inject_text") or "").strip()
    changed = _changed_tool_claims(old_text, new_text)

    # Parse claim / waiver flags (JSON each — typed parse errors, exit 2).
    claims, waives = {}, {}
    for raw in (args.claim or []):
        try:
            c = json.loads(raw)
            tok, src, ev = c["token"], c["source"], c["evidence"]
        except (ValueError, KeyError, TypeError):
            _typed("refused", {"reason": "claim_malformed", "claim": raw})
            sys.stderr.write("[boot-injection refresh] REFUSED: claim_malformed "
                             "(JSON with token/source/evidence required)\n")
            return 2
        claims[tok] = {"source": src, "evidence": ev}
    for raw in (args.waive_claim or []):
        try:
            w = json.loads(raw)
            tok, reason = w["token"], w["reason"]
        except (ValueError, KeyError, TypeError):
            _typed("refused", {"reason": "waive_claim_malformed", "waive_claim": raw})
            sys.stderr.write("[boot-injection refresh] REFUSED: waive_claim_malformed "
                             "(JSON with token/reason required)\n")
            return 2
        waives[tok] = reason

    # Typo guard: a claim/waiver naming a token whose claim did NOT change is a
    # caller error (tells the caller exactly which tokens changed), exit 2.
    unknown = sorted((set(claims) | set(waives)) - set(changed))
    if unknown:
        _typed("refused", {"reason": "claim_token_not_changed", "tokens": unknown,
                           "changed_tool_claims": changed})
        sys.stderr.write(f"[boot-injection refresh] REFUSED: claim_token_not_changed "
                         f"{unknown} (changed: {changed})\n")
        return 2

    # THE GATE — fires BEFORE any side effect; refusal leaves the registry untouched.
    refusals, verified, waived = [], [], []
    for tok in changed:
        if tok in waives:
            waived.append({"token": tok, "reason": waives[tok]})
            continue
        if tok not in claims:
            refusals.append({"token": tok, "reason": "claim_missing"})
            continue
        src = Path(claims[tok]["source"])
        if not src.is_absolute():
            src = zone_root / src
        if not src.is_file():
            refusals.append({"token": tok, "reason": "source_unresolved",
                             "source": claims[tok]["source"]})
            continue
        source_bytes = src.read_bytes()
        evidence = claims[tok]["evidence"]
        if not evidence or evidence not in source_bytes.decode("utf-8", errors="replace"):
            refusals.append({"token": tok, "reason": "evidence_not_in_source",
                             "source": claims[tok]["source"]})
            continue
        verified.append({
            "token": tok,
            "source": claims[tok]["source"],
            "evidence": evidence,
            # computed-at-write, never transcribed (t628 born law)
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        })
    if refusals:
        _typed("refused", {"reason": "claim_gate_refused", "refusals": refusals,
                           "changed_tool_claims": changed})
        sys.stderr.write(f"[boot-injection refresh] CLAIM-GATE REFUSED: {refusals}\n")
        return 3

    receipt = {
        "gate": "refresh-claim-gate-v1",
        "verified_at_tic": args.tic,
        "changed_tool_claims": changed,
        "verified": verified,
        "waived": waived,
    }
    row = dict(target)
    row["inject_text"] = new_text
    row["refreshed_at_tic"] = args.tic          # existing WHY receipt, unchanged shape
    row["refresh_reason"] = args.refresh_reason  # existing WHY receipt, unchanged shape
    row["claim_verification"] = receipt          # the new WHAT receipt, bound alongside

    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
    from atomic_append import atomic_append_jsonl  # lazy: render path never imports this
    atomic_append_jsonl(str(reg), row)

    _typed("refreshed", {"injection_id": args.injection_id, "tic": args.tic,
                         "claim_verification": receipt})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--tic", type=int, required=True)
    r.add_argument("--audience", required=True,
                   help="orchestrator | citizens | ent_<id>")
    r.add_argument("--zone-root", default=None,
                   help="explicit canonical zone root (required for the installed copy)")
    r.add_argument("--max-chars", type=int, default=0,
                   help="budget the joined output; 0 = unbounded (default, back-compat). "
                        "Lowest-priority pointers seal first with a SEALED marker.")
    f = sub.add_parser("refresh")
    f.add_argument("--injection-id", required=True)
    f.add_argument("--tic", type=int, required=True)
    f.add_argument("--refresh-reason", required=True,
                   help="the existing WHY receipt — why the injection text changed")
    f.add_argument("--inject-text", default=None)
    f.add_argument("--inject-text-file", default=None)
    f.add_argument("--claim", action="append", default=[],
                   help='JSON {"token","source","evidence"} — evidence substring is '
                        "verified against the resolved source AT REFRESH TIME")
    f.add_argument("--waive-claim", action="append", default=[],
                   help='JSON {"token","reason"} — explicit, receipted waiver '
                        "(visible in claim_verification.waived; surface-don't-hide)")
    f.add_argument("--zone-root", default=None)
    args = ap.parse_args()

    if args.cmd == "refresh":
        # Governance WRITE verb: fail-CLOSED, never wrapped in render's fail-soft.
        return _refresh(args)

    zone_root = _zone_root(Path(__file__).resolve().parent, args.zone_root)
    if zone_root is None:
        return 0  # fail-soft: no zone, no injection
    try:
        text = render(zone_root, args.tic, args.audience, args.max_chars)
    except Exception as e:  # never break a boot
        sys.stderr.write(f"[boot-injection] render error: {e}\n")
        return 0
    if text:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
