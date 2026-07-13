#!/usr/bin/env python3
"""Verify harness — boot-injection refresh claim-gate.

bk-boot-injection-refresh-claim-gate (admitted /review 624, lowered t626, BUILT t630).
Doctrine home: constitution-ledger#refresh-is-inscription-event-vacuous-green-conceals.
Exercises the four lowered fragments:

  wave 0 obj-0  the refresh path carries a claim-gate: a refresh that changes what
                a TOOL is claimed to DO verifies the new inject_text against the
                tool's source at refresh time (fail-closed, before any side effect)
  wave 0 obj-1  refreshed rows bind the WHAT-verification receipt alongside the
                existing refreshed_at_tic + refresh_reason WHY receipt
  wave 1 obj-0  claim-gate parity with the handoff claim-gate (verify against the
                real artifact before the claim lands); WHY receipt behavior and the
                render path unchanged (OLD-vs-NEW byte parity regression)
  wave 1 obj-1  cgg sync parity (versioning lands in context-grapple-gun — checked
                at commit, not here)

Every arm runs through the REAL CLI argv surface (subprocess) against throwaway
fixture zones (self-locating-artifact-test-isolation: --zone-root pins the root;
the real registry is never written). The OLD-vs-NEW parity arm additionally runs
render READ-ONLY against the real zone when one resolves. Both arms of every
documented conditional get a fixture (selftest-fixtures-must-exercise-
documented-conditional-paths).

Run: python3 test_boot_injection_refresh_claim_gate.py [--old-rev REV]
Exit 0 = all arms pass; exit 1 = failure (named arm).
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import hashlib

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BOOT_INJECTION = os.path.join(SCRIPTS_DIR, "boot-injection.py")
CGG_ROOT = os.path.dirname(os.path.dirname(SCRIPTS_DIR))  # context-grapple-gun/
REPO_REL = "cgg-runtime/scripts/boot-injection.py"


def run(script, *argv):
    return subprocess.run([sys.executable, script, *argv],
                          capture_output=True, text=True)


def make_zone(root, name):
    zone = os.path.join(root, name)
    os.makedirs(os.path.join(zone, "audit-logs", "boot-injections"), exist_ok=True)
    pathlib.Path(zone, ".ticzone").write_text(
        json.dumps({"name": "fixture-zone"}), encoding="utf-8")
    return zone


def write_registry(zone, rows):
    reg = pathlib.Path(zone, "audit-logs", "boot-injections", "active.jsonl")
    reg.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return reg


def fixture_rows():
    return [
        {"injection_id": "fx-plain", "inject_from_tic": 1, "inject_until_tic": 9999,
         "reminder_at_tic": None, "audience": "all", "priority": 30,
         "status": "active",
         "inject_text": "Standing pointer current as of tic 5. fixture-tool.py "
                        "re-derives the board from the live table."},
        {"injection_id": "fx-reminder", "inject_from_tic": 1, "inject_until_tic": 9999,
         "reminder_at_tic": 2, "audience": "orchestrator", "priority": 10,
         "status": "active", "inject_text": "pre-reminder text",
         "reminder_text": "REMINDER: re-evaluate this lane."},
        {"injection_id": "fx-retired", "inject_from_tic": 1, "inject_until_tic": 9999,
         "reminder_at_tic": None, "audience": "all", "status": "retired",
         "inject_text": "should never render or refresh"},
        {"injection_id": "fx-notool", "inject_from_tic": 1, "inject_until_tic": 9999,
         "reminder_at_tic": None, "audience": "all", "priority": 50,
         "status": "active",
         "inject_text": "A pointer with no tool claims at all, tic 5 currency."},
    ]


def write_fixture_tool(zone):
    tool = pathlib.Path(zone, "scripts", "fixture-tool.py")
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text('#!/usr/bin/env python3\n'
                    'BOARD_MD = "frozen-table.md"  # sole identity source\n'
                    'def rederive():\n    return BOARD_MD\n', encoding="utf-8")
    return tool


def main():
    old_rev = "HEAD"
    if "--old-rev" in sys.argv:
        old_rev = sys.argv[sys.argv.index("--old-rev") + 1]

    failures = []
    results = {}

    def arm(name, ok, detail=""):
        results[name] = "PASS" if ok else f"FAIL {detail}"
        if not ok:
            failures.append(f"{name}: {detail}")

    with tempfile.TemporaryDirectory(prefix="boot-inj-gate-fixture-") as tmp:

        # ------------------------------------------------------------------
        # ARM 1 — OLD-vs-NEW render byte parity (render path untouched).
        # ------------------------------------------------------------------
        old_copy = os.path.join(tmp, "boot-injection-old.py")
        show = subprocess.run(["git", "-C", CGG_ROOT, "show", f"{old_rev}:{REPO_REL}"],
                              capture_output=True, text=True)
        if show.returncode != 0:
            arm("render_parity_old_vs_new", False,
                f"git show failed: {show.stderr.strip()[:200]}")
        else:
            pathlib.Path(old_copy).write_text(show.stdout, encoding="utf-8")
            zone = make_zone(tmp, "parity-zone")
            write_registry(zone, fixture_rows())
            parity_ok = True
            detail = ""
            for tic, aud, mx in [(5, "orchestrator", "0"), (5, "citizens", "0"),
                                 (5, "ent_fx", "0"), (5, "orchestrator", "60")]:
                a = run(old_copy, "render", "--tic", str(tic), "--audience", aud,
                        "--zone-root", zone, "--max-chars", mx)
                b = run(BOOT_INJECTION, "render", "--tic", str(tic), "--audience", aud,
                        "--zone-root", zone, "--max-chars", mx)
                if a.stdout != b.stdout or a.returncode != b.returncode:
                    parity_ok = False
                    detail = f"divergence at tic={tic} aud={aud} max={mx}"
                    break
            # real-zone READ-ONLY leg (render only; skipped silently if no zone).
            real = run(BOOT_INJECTION, "render", "--tic", "630",
                       "--audience", "orchestrator")
            real_old = run(old_copy, "render", "--tic", "630",
                           "--audience", "orchestrator")
            if real.stdout != real_old.stdout:
                parity_ok = False
                detail = "real-zone read-only render diverged OLD vs NEW"
            arm("render_parity_old_vs_new", parity_ok, detail)

        # ------------------------------------------------------------------
        # ARM 2 — refresh with NO tool-claim change: passes, binds WHY + WHAT
        # receipts, appends without touching prior bytes.
        # ------------------------------------------------------------------
        zone = make_zone(tmp, "happy-zone")
        reg = write_registry(zone, fixture_rows())
        before = reg.read_bytes()
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-notool",
                "--tic", "630", "--refresh-reason", "currency bump",
                "--inject-text",
                "A pointer with no tool claims at all, tic 630 currency.",
                "--zone-root", zone)
        after = reg.read_bytes()
        ok = p.returncode == 0 and after.startswith(before) and len(after) > len(before)
        row = json.loads(after[len(before):].decode()) if ok else {}
        ok = (ok and row.get("refreshed_at_tic") == 630
              and row.get("refresh_reason") == "currency bump"
              and row.get("claim_verification", {}).get("changed_tool_claims") == []
              and row.get("claim_verification", {}).get("gate") == "refresh-claim-gate-v1")
        arm("refresh_no_claim_change_passes", ok,
            f"rc={p.returncode} out={p.stdout[:200]}")

        # latest-per-id: render now shows the refreshed text.
        r = run(BOOT_INJECTION, "render", "--tic", "630", "--audience", "ent_x",
                "--zone-root", zone)
        arm("render_shows_refreshed_text",
            "tic 630 currency" in r.stdout and "tic 5 currency" not in r.stdout,
            r.stdout[:200])

        # ------------------------------------------------------------------
        # ARM 3 — changed tool-claim WITHOUT evidence: exit 3, ZERO side effects.
        # ------------------------------------------------------------------
        zone = make_zone(tmp, "refuse-zone")
        reg = write_registry(zone, fixture_rows())
        write_fixture_tool(zone)
        before = reg.read_bytes()
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "630", "--refresh-reason", "elevate ritual",
                "--inject-text",
                "fixture-tool.py re-derives the board from LIVE inputs every tic.",
                "--zone-root", zone)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("changed_claim_without_evidence_refused_exit3",
            p.returncode == 3 and reg.read_bytes() == before
            and out.get("reason") == "claim_gate_refused"
            and out["refusals"][0]["reason"] == "claim_missing"
            and p.stderr.strip() != "",
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 4 — changed claim WITH matching evidence: passes, sha256
        # computed-at-write matches the real source bytes.
        # ------------------------------------------------------------------
        tool = write_fixture_tool(zone)
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "630", "--refresh-reason", "elevate ritual",
                "--inject-text",
                "fixture-tool.py re-derives the board from its frozen table.",
                "--claim", json.dumps({"token": "fixture-tool.py",
                                       "source": "scripts/fixture-tool.py",
                                       "evidence": 'BOARD_MD = "frozen-table.md"'}),
                "--zone-root", zone)
        ok = p.returncode == 0
        if ok:
            rec = json.loads(p.stdout)["claim_verification"]
            want = hashlib.sha256(tool.read_bytes()).hexdigest()
            ok = (rec["verified"][0]["source_sha256"] == want
                  and rec["changed_tool_claims"] == ["fixture-tool.py"]
                  and rec["waived"] == [])
        arm("changed_claim_with_evidence_passes_sha_computed_at_write", ok,
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 5 — evidence NOT in source: exit 3, reason-coded.
        # ------------------------------------------------------------------
        before = reg.read_bytes()
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "631", "--refresh-reason", "drift again",
                "--inject-text",
                "fixture-tool.py now reads io-map and ts_router live.",
                "--claim", json.dumps({"token": "fixture-tool.py",
                                       "source": "scripts/fixture-tool.py",
                                       "evidence": "reads io-map live"}),
                "--zone-root", zone)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("evidence_not_in_source_refused_exit3",
            p.returncode == 3 and reg.read_bytes() == before
            and out.get("refusals", [{}])[0].get("reason") == "evidence_not_in_source",
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 6 — source unresolvable: exit 3, reason-coded.
        # ------------------------------------------------------------------
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "631", "--refresh-reason", "drift again",
                "--inject-text",
                "fixture-tool.py now reads io-map and ts_router live.",
                "--claim", json.dumps({"token": "fixture-tool.py",
                                       "source": "scripts/no-such-tool.py",
                                       "evidence": "anything"}),
                "--zone-root", zone)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("source_unresolved_refused_exit3",
            p.returncode == 3
            and out.get("refusals", [{}])[0].get("reason") == "source_unresolved",
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 7 — explicit waiver: passes, waiver VISIBLE in the receipt.
        # ------------------------------------------------------------------
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "631", "--refresh-reason", "waived refresh",
                "--inject-text",
                "external-runner.sh handles dispatch now (source lives off-zone).",
                "--waive-claim", json.dumps({"token": "external-runner.sh",
                                             "reason": "source off-zone; verified "
                                                       "manually at t631"}),
                "--zone-root", zone)
        ok = p.returncode == 0
        if ok:
            rec = json.loads(p.stdout)["claim_verification"]
            ok = (rec["waived"] == [{"token": "external-runner.sh",
                                     "reason": "source off-zone; verified manually "
                                               "at t631"}]
                  and rec["verified"] == [])
        arm("waiver_passes_and_is_visible", ok,
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 8 — claim naming an UNCHANGED token: exit 2 typo guard.
        # ------------------------------------------------------------------
        zone8 = make_zone(tmp, "typo-zone")
        write_registry(zone8, fixture_rows())
        write_fixture_tool(zone8)
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "630", "--refresh-reason", "text-only tweak",
                "--inject-text",
                "Standing pointer current as of tic 630. fixture-tool.py "
                "re-derives the board from the live table.",
                "--claim", json.dumps({"token": "fixture-tool.py",
                                       "source": "scripts/fixture-tool.py",
                                       "evidence": "BOARD_MD"}),
                "--zone-root", zone8)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("claim_for_unchanged_token_exit2",
            p.returncode == 2 and out.get("reason") == "claim_token_not_changed",
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 9 — a REMOVED tool mention owes nothing (no new claim).
        # ------------------------------------------------------------------
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "630", "--refresh-reason", "drop the tool mention",
                "--inject-text",
                "Standing pointer current as of tic 630; board ritual retired here.",
                "--zone-root", zone8)
        ok = p.returncode == 0
        if ok:
            rec = json.loads(p.stdout)["claim_verification"]
            ok = rec["changed_tool_claims"] == [] and rec["verified"] == []
        arm("removed_tool_mention_owes_nothing", ok,
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 10 — target errors, both arms: missing id / non-active target.
        # ------------------------------------------------------------------
        p1 = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-nonexistent",
                 "--tic", "630", "--refresh-reason", "x",
                 "--inject-text", "y", "--zone-root", zone8)
        p2 = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-retired",
                 "--tic", "630", "--refresh-reason", "x",
                 "--inject-text", "y", "--zone-root", zone8)
        o1 = json.loads(p1.stdout) if p1.stdout.strip() else {}
        o2 = json.loads(p2.stdout) if p2.stdout.strip() else {}
        arm("refresh_target_errors_exit2",
            p1.returncode == 2 and o1.get("reason") == "refresh_target_missing"
            and p2.returncode == 2 and o2.get("reason") == "refresh_target_not_active",
            f"rc1={p1.returncode} rc2={p2.returncode}")

        # ------------------------------------------------------------------
        # ARM 11 — text-source cardinality, both arms: both given / neither.
        # ------------------------------------------------------------------
        tf = pathlib.Path(tmp, "text.txt")
        tf.write_text("from file", encoding="utf-8")
        p1 = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-notool",
                 "--tic", "630", "--refresh-reason", "x",
                 "--inject-text", "y", "--inject-text-file", str(tf),
                 "--zone-root", zone8)
        p2 = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-notool",
                 "--tic", "630", "--refresh-reason", "x", "--zone-root", zone8)
        arm("text_source_not_exactly_one_exit2",
            p1.returncode == 2 and p2.returncode == 2,
            f"rc1={p1.returncode} rc2={p2.returncode}")

        # ------------------------------------------------------------------
        # ARM 12 — malformed claim JSON: exit 2, typed.
        # ------------------------------------------------------------------
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-notool",
                "--tic", "630", "--refresh-reason", "x",
                "--inject-text", "mentions changed-tool.py now",
                "--claim", "not-json", "--zone-root", zone8)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("malformed_claim_exit2",
            p.returncode == 2 and out.get("reason") == "claim_malformed",
            f"rc={p.returncode} out={p.stdout[:200]}")

        # ------------------------------------------------------------------
        # ARM 13 — registry missing: exit 2 (fail-closed, not fail-soft).
        # ------------------------------------------------------------------
        zone13 = make_zone(tmp, "noreg-zone")
        os.remove(os.path.join(zone13, "audit-logs", "boot-injections",
                               "active.jsonl")) if os.path.exists(
            os.path.join(zone13, "audit-logs", "boot-injections",
                         "active.jsonl")) else None
        p = run(BOOT_INJECTION, "refresh", "--injection-id", "fx-plain",
                "--tic", "630", "--refresh-reason", "x",
                "--inject-text", "y", "--zone-root", zone13)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        arm("registry_missing_exit2",
            p.returncode == 2 and out.get("reason") == "registry_missing",
            f"rc={p.returncode} out={p.stdout[:200]}")

    print(json.dumps({"arms": results,
                      "passed": len(results) - len(failures),
                      "failed": len(failures)}, indent=1))
    if failures:
        for f in failures:
            sys.stderr.write(f"FAIL {f}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
