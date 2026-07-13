#!/usr/bin/env python3
"""
ratify-intake-sweep.py — the ratify-time volatile-sweep intake tooth.

bk-ratify-intake-volatile-sweep (admitted /review 611 PROMOTE-as-refinement,
cgg-ledger#ratification-freezes-embedded-volatile-state-ratify-time-volatile-sweep;
build leg named in the admission; lowered t626; BUILT t631).

When a data surface is ratified as an authoritative baseline, the ratification
freezes every VOLATILE value embedded in it at ratify-time — computed-per-tic
gate lines, due markers, counts — which then age silently UNDER THE
RATIFICATION'S AUTHORITY (the lived cohort: four offices carried a baked
"/review 427 due tic 427" active_arcs entry for ~180 tics while the live
obligation line was computed per-tic by office-worldview.py).

This tool is the missing intake tooth, wired at the LOCUS the admission names
(ratification intake). The CHECK is the physics; the mutation verbs are
conveniences for the lexically-safe cases:

  sweep <surface>                          detect embedded volatile values
      exit 0  clean, or every finding dispositioned (ratification may proceed)
      exit 3  undispositioned volatile stowaways (typed refusal — ratification
              must NOT proceed until each is stripped / stamped / accept-receipted)
      exit 2  usage / target errors
  strip <surface> --finding ID --tic N     remove the finding's line
      (single-owner discipline: a computed producer owns the value; its static
      copy is a latent contradiction, not documentation)
  stamp <surface> --finding ID --tic N [--ttl-tics T]
      annotate the value in place with last_verified_tic / ttl_tics
      (Volatility-Handling law: volatile snapshots carry their freshness)
  accept <surface> --finding ID --tic N --reason "…"
      receipted human-judgment valve for detector false positives — visible in
      receipts and in every later sweep of the surface, never silent

Fail-closed mutation guarantees:
  - strip on a JSON surface that would no longer parse REFUSES typed
    (strip_would_corrupt_surface, exit 3) with the surface byte-untouched
  - stamp with no lexically-safe in-place site REFUSES typed
    (stamp_not_derivable_for_surface, exit 3) with the surface byte-untouched;
    the author stamps manually (structure-aware) and re-sweeps — the re-sweep
    recognizes last_verified/ttl markers and the finding clears
  - every disposition appends a receipt (atomic JSONL) carrying the surface
    sha256 BEFORE and AFTER, computed at write

APERTURE (truth boundary, do not overclaim): detection is LEXICAL — a
pattern-class table over line text. A volatile value expressed outside the
lexicon sits outside this gate's aperture; behavioral discipline is still owed
by the ratifying author. `accept` exists because a lexical detector has false
positives; it is always receipted, never silent.

Finding identity is content-derived (surface basename + class + normalized
excerpt), line-number independent — a disposition receipt survives unrelated
edits to the surface.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)
from lib.atomic_append import atomic_append_jsonl  # noqa: E402
from zone_root import resolve_zone_root  # noqa: E402

RECEIPTS_REL = "audit-logs/governance/ratify-intake-sweeps/receipts.jsonl"

# ---------------------------------------------------------------------------
# Content table (engine/content separation): the volatile-pattern lexicon.
# Classes come verbatim from the admission: "computed-per-tic gate lines,
# due markers, counts". Edit the TABLE to extend coverage; the engine
# (finding lifecycle, exits, receipts) does not change.
# ---------------------------------------------------------------------------
DUE_MARKER_PATTERNS = [
    re.compile(r"\bdue\s+(?:at\s+)?tic\s+\d+", re.IGNORECASE),
    re.compile(r"\bdue[_-]tic\"?\s*[:=]\s*\d+", re.IGNORECASE),
    re.compile(r"\bmatures?\s+(?:at\s+)?tic\s+\d+", re.IGNORECASE),
    re.compile(r"\breeval[_-]tic\"?\s*[:=]\s*\d+", re.IGNORECASE),
]
COUNT_SNAPSHOT_PATTERNS = [
    re.compile(r"\b\d+\s+(?:active|pending|open|stale|unresolved)\b", re.IGNORECASE),
    re.compile(r"\b(?:active|pending|open|unresolved)[_-]count\"?\s*[:=]\s*\d+", re.IGNORECASE),
]
# Containers whose contents a computed producer owns per-tic (the lived case:
# office-worldview.py computes obligation/arc lines from tic_context).
COMPUTED_PRODUCER_CONTAINERS = re.compile(
    r"\b(active_arcs|obligations|cadence_due|gate_lines)\b"
)

# Suppressions — NOT findings:
ALREADY_STAMPED = re.compile(r"last[_-]?verified[_-]?tic|ttl[_-]?tics", re.IGNORECASE)
PROVENANCE_STAMP = re.compile(
    r"\b(born[_-]tic|promoted[_-]tic|last[_-]touched[_-]tic|drained[_-]at[_-]tic"
    r"|probed[_-]at[_-]tic|resolved[_-]at[_-]tic|lowered[_-]at[_-]tic"
    r"|re[_-]drained[_-]at[_-]tic|created[_-]at|frozen[_-]at|state[_-]entered[_-]at"
    r"|completed[_-]at[_-]tic|deactivated[_-]at[_-]tic|activated[_-]at[_-]tic)\b",
    re.IGNORECASE,
)
HASH_LINE = re.compile(r"\b(sha256|sha16|_hash|hash_)\b", re.IGNORECASE)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def finding_id(surface_base, cls, excerpt):
    norm = re.sub(r"\s+", " ", excerpt.strip())
    return hashlib.sha256(f"{surface_base}|{cls}|{norm}".encode()).hexdigest()[:16]


def detect(surface_path):
    """Lexical sweep. Returns a list of finding dicts (undisposed view)."""
    text = open(surface_path, "r", encoding="utf-8").read()
    lines = text.splitlines()
    base = os.path.basename(surface_path)
    findings = []
    # Track whether we are lexically inside a computed-producer container.
    # Line-based heuristic: a container key line opens scope until a line that
    # closes the bracket at same-or-lower indent OR another key at same level.
    container_depth = None  # indent of the open container, None = outside
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if container_depth is not None:
            # leave scope when we return to same-or-lower indent on a new key
            # or a closing bracket at same-or-lower indent
            if stripped and indent <= container_depth and not stripped.startswith(("]", "}", ")")):
                container_depth = None
            elif stripped.startswith(("]", "}")) and indent <= container_depth:
                container_depth = None
        if COMPUTED_PRODUCER_CONTAINERS.search(line) and (":" in line or "=" in line):
            container_depth = indent
            continue  # the key line itself is structure, not a value
        if not stripped:
            continue
        if ALREADY_STAMPED.search(line):
            continue  # already carries freshness — Volatility law satisfied
        if PROVENANCE_STAMP.search(line):
            continue  # historical fact, not an aging claim
        if HASH_LINE.search(line):
            continue
        hit_cls = None
        for pat in DUE_MARKER_PATTERNS:
            if pat.search(line):
                hit_cls = "due_marker"
                break
        if hit_cls is None:
            for pat in COUNT_SNAPSHOT_PATTERNS:
                if pat.search(line):
                    hit_cls = "count_snapshot"
                    break
        if hit_cls is None:
            continue
        inside_computed = container_depth is not None
        cls = "computed_gate_line" if (inside_computed and hit_cls == "due_marker") else hit_cls
        findings.append({
            "finding_id": finding_id(base, cls, stripped),
            "class": cls,
            "line_no": i,
            "excerpt": stripped[:240],
            "suggested_disposition": "strip" if cls == "computed_gate_line" else "stamp",
            "suggestion_basis": (
                "computed producer owns per-tic gate/arc lines (single-owner discipline)"
                if cls == "computed_gate_line"
                else "stamp last_verified/TTL per the Volatility-Handling law"
            ),
        })
    return findings


def load_dispositions(receipts_path, surface_base):
    """Latest-per-finding-id disposition acts for this surface."""
    acts = {}
    if not os.path.exists(receipts_path):
        return acts
    with open(receipts_path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if row.get("surface_base") != surface_base:
                continue
            fid = row.get("finding_id")
            if fid:
                acts[fid] = row  # latest wins (append-only)
    return acts


def emit(payload, stream=sys.stdout):
    json.dump(payload, stream, indent=1)
    stream.write("\n")


def receipts_path_for(args):
    zone = resolve_zone_root()
    return os.path.join(zone, RECEIPTS_REL)


def cmd_sweep(args):
    surface = args.surface
    if not os.path.isfile(surface):
        emit({"status": "error", "error": "surface_not_found", "surface": surface})
        print(f"ratify-intake-sweep: surface not found: {surface}", file=sys.stderr)
        return 2
    receipts = receipts_path_for(args)
    findings = detect(surface)
    acts = load_dispositions(receipts, os.path.basename(surface))
    open_findings, dispositioned = [], []
    for f in findings:
        act = acts.get(f["finding_id"])
        if act and act.get("act") == "accept":
            dispositioned.append({**f, "disposition": "accepted",
                                  "reason": act.get("reason"),
                                  "receipted_at_tic": act.get("tic")})
        else:
            # strip/stamp receipts describe PAST mutations; if the finding
            # still detects on current bytes, the disposition did not land —
            # it stays OPEN (fail-closed; re-sweep is the gate).
            open_findings.append(f)
    payload = {
        "verb": "sweep",
        "surface": surface,
        "surface_sha256": sha256_file(surface),
        "aperture": "lexical (pattern-class table over line text); values outside the lexicon are outside this gate — behavioral discipline still owed",
        "findings_open": open_findings,
        "findings_accepted": dispositioned,
        "clean": not open_findings,
    }
    if open_findings:
        payload["status"] = "refused"
        payload["refusal"] = "volatile_stowaways_undispositioned"
        payload["demand"] = "strip (computed producer owns it) | stamp last_verified/TTL | accept --reason (receipted)"
        emit(payload)
        print(
            f"ratify-intake-sweep: REFUSED — {len(open_findings)} undispositioned volatile "
            f"stowaway(s) in {os.path.basename(surface)}; ratification must not proceed",
            file=sys.stderr,
        )
        return 3
    payload["status"] = "clean"
    emit(payload)
    return 0


def _find_open_finding(surface, fid):
    for f in detect(surface):
        if f["finding_id"] == fid:
            return f
    return None


def _receipt(args, surface, act, fid, before_sha, after_sha, extra=None):
    row = {
        "act": act,
        "finding_id": fid,
        "surface": os.path.relpath(surface, resolve_zone_root()) if os.path.isabs(surface) else surface,
        "surface_base": os.path.basename(surface),
        "tic": args.tic,
        "surface_sha256_before": before_sha,
        "surface_sha256_after": after_sha,
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": "ratify-intake-sweep.py",
    }
    if extra:
        row.update(extra)
    atomic_append_jsonl(receipts_path_for(args), row)
    return row


def cmd_strip(args):
    surface = args.surface
    if not os.path.isfile(surface):
        emit({"status": "error", "error": "surface_not_found", "surface": surface})
        return 2
    f = _find_open_finding(surface, args.finding)
    if f is None:
        emit({"status": "error", "error": "finding_not_open", "finding_id": args.finding})
        print("ratify-intake-sweep: no open finding with that id on current bytes", file=sys.stderr)
        return 2
    before = sha256_file(surface)
    text = open(surface, "r", encoding="utf-8").read()
    lines = text.splitlines(keepends=True)
    idx = f["line_no"] - 1
    new_text = "".join(lines[:idx] + lines[idx + 1:])
    if surface.endswith(".json"):
        try:
            json.loads(new_text)
        except json.JSONDecodeError:
            emit({"status": "refused", "refusal": "strip_would_corrupt_surface",
                  "finding_id": args.finding, "surface": surface,
                  "detail": "removing the line leaves unparseable JSON; strip manually (structure-aware) and re-sweep"})
            print("ratify-intake-sweep: REFUSED strip — result would not parse; surface untouched", file=sys.stderr)
            return 3
    with open(surface, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    row = _receipt(args, surface, "strip", args.finding, before, sha256_file(surface),
                   {"class": f["class"], "excerpt": f["excerpt"]})
    emit({"status": "stripped", "receipt": row})
    return 0


def cmd_stamp(args):
    surface = args.surface
    if not os.path.isfile(surface):
        emit({"status": "error", "error": "surface_not_found", "surface": surface})
        return 2
    f = _find_open_finding(surface, args.finding)
    if f is None:
        emit({"status": "error", "error": "finding_not_open", "finding_id": args.finding})
        return 2
    before = sha256_file(surface)
    stamp = f"last_verified_tic: {args.tic}" + (f" · ttl_tics: {args.ttl_tics}" if args.ttl_tics else "")
    text = open(surface, "r", encoding="utf-8").read()
    lines = text.splitlines(keepends=True)
    idx = f["line_no"] - 1
    line = lines[idx]
    eol = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")
    if surface.endswith(".json"):
        # Lexically safe only when the line carries a JSON string value we can
        # append inside: …"value"  or  …"value",
        m = re.match(r'^(.*")([,]?)\s*$', body)
        if m and body.count('"') >= 2:
            new_body = m.group(1)[:-1] + f' [{stamp}]"' + m.group(2)
            new_text = "".join(lines[:idx]) + new_body + eol + "".join(lines[idx + 1:])
            try:
                json.loads(new_text)
            except json.JSONDecodeError:
                emit({"status": "refused", "refusal": "stamp_not_derivable_for_surface",
                      "finding_id": args.finding,
                      "detail": "no lexically-safe in-place stamp site; stamp manually (structure-aware) and re-sweep"})
                print("ratify-intake-sweep: REFUSED stamp — surface untouched", file=sys.stderr)
                return 3
        else:
            emit({"status": "refused", "refusal": "stamp_not_derivable_for_surface",
                  "finding_id": args.finding,
                  "detail": "finding line carries no JSON string value; stamp manually (structure-aware) and re-sweep"})
            print("ratify-intake-sweep: REFUSED stamp — surface untouched", file=sys.stderr)
            return 3
    else:
        new_text = "".join(lines[:idx]) + body + f"  [{stamp}]" + eol + "".join(lines[idx + 1:])
    with open(surface, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    row = _receipt(args, surface, "stamp", args.finding, before, sha256_file(surface),
                   {"class": f["class"], "excerpt": f["excerpt"],
                    "last_verified_tic": args.tic, "ttl_tics": args.ttl_tics})
    emit({"status": "stamped", "receipt": row})
    return 0


def cmd_accept(args):
    surface = args.surface
    if not os.path.isfile(surface):
        emit({"status": "error", "error": "surface_not_found", "surface": surface})
        return 2
    f = _find_open_finding(surface, args.finding)
    if f is None:
        emit({"status": "error", "error": "finding_not_open", "finding_id": args.finding})
        return 2
    sha = sha256_file(surface)
    row = _receipt(args, surface, "accept", args.finding, sha, sha,
                   {"class": f["class"], "excerpt": f["excerpt"], "reason": args.reason})
    emit({"status": "accepted", "receipt": row,
          "note": "receipted human-judgment valve — visible in every later sweep, never silent"})
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1].strip())
    sub = p.add_subparsers(dest="verb", required=True)

    sp = sub.add_parser("sweep", help="detect embedded volatile values (exit 3 = fail-closed refusal)")
    sp.add_argument("surface")
    sp.set_defaults(fn=cmd_sweep)

    st = sub.add_parser("strip", help="remove a finding's line (single-owner discipline)")
    st.add_argument("surface")
    st.add_argument("--finding", required=True)
    st.add_argument("--tic", type=int, required=True)
    st.set_defaults(fn=cmd_strip)

    sm = sub.add_parser("stamp", help="annotate last_verified/TTL in place")
    sm.add_argument("surface")
    sm.add_argument("--finding", required=True)
    sm.add_argument("--tic", type=int, required=True)
    sm.add_argument("--ttl-tics", type=int, default=None)
    sm.set_defaults(fn=cmd_stamp)

    ac = sub.add_parser("accept", help="receipted false-positive valve (requires --reason)")
    ac.add_argument("surface")
    ac.add_argument("--finding", required=True)
    ac.add_argument("--tic", type=int, required=True)
    ac.add_argument("--reason", required=True)
    ac.set_defaults(fn=cmd_accept)

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        # argparse exits 2 on usage errors — preserve that contract
        raise
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
