#!/usr/bin/env python3
"""Verify harness — ratify-time volatile-sweep intake tooth.

bk-ratify-intake-volatile-sweep (admitted /review 611 PROMOTE-as-refinement,
lowered t626, BUILT t631). Exercises the two lowered fragments:

  wave 0 obj-0  the ratification-intake lane sweeps the candidate surface for
                embedded volatile values; each is STRIPPED (computed producer
                owns it, single-owner) or STAMPED last-verified/TTL
  wave 1 obj-0  no ratified baseline carries a baked volatile value that ages
                silently under the ratification's authority (the stale-baseline
                class is closed at intake — fail-closed exit 3 until every
                stowaway is dispositioned)

Every arm drives the REAL CLI argv surface (subprocess, never import-and-call
for the verdict arms). Fixture zones are throwaway temp dirs carrying their own
.ticzone, with CLAUDE_PROJECT_DIR pinned so receipts NEVER touch the real zone
(self-locating-artifact-test-isolation). Both arms of every documented
conditional get a fixture (selftest-fixtures-must-exercise-documented-
conditional-paths). The real-zone leg is READ-ONLY (sweep writes nothing) with
byte parity asserted (real_zone_readonly probe class).

Run: python3 test_ratify_intake_volatile_sweep.py
Exit 0 = all arms pass; exit 1 = failure (named arm).
"""

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SWEEP = os.path.join(SCRIPTS_DIR, "ratify-intake-sweep.py")

LIVED_COHORT_LINE = "/review 427 due tic 427"  # the ~180-tic stale active_arcs shape


def run(zone, *argv):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=zone)
    return subprocess.run(
        [sys.executable, SWEEP, *argv],
        capture_output=True, text=True, cwd=zone, env=env,
    )


def make_zone(tmp, name):
    zone = os.path.join(tmp, name)
    os.makedirs(os.path.join(zone, "audit-logs"), exist_ok=True)
    pathlib.Path(zone, ".ticzone").write_text('{"name":"fixture-zone"}', encoding="utf-8")
    return zone


def write(zone, name, text):
    p = os.path.join(zone, name)
    pathlib.Path(p).write_text(text, encoding="utf-8")
    return p


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def out_json(cp):
    return json.loads(cp.stdout)


LIVED_FIXTURE = """{
 "office": "ent_fixture",
 "active_arcs": [
  "the fidelity drill (decouple->simulate->rehydrate)",
  "%s",
  "keep this arc"
 ],
 "born_tic": 607
}
""" % LIVED_COHORT_LINE


def main():
    failures = []
    results = {}

    def arm(name, ok, detail=""):
        results[name] = "PASS" if ok else f"FAIL {detail}"
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="ratify-sweep-fixture-") as tmp:

        # ---- arm 1/2: sweep clean surface -> exit 0; dirty -> exit 3 typed
        z = make_zone(tmp, "z1")
        clean = write(z, "clean.md", "# Orientation\nA stable statement of purpose.\n")
        cp = run(z, "sweep", clean)
        arm("sweep_clean_exit0", cp.returncode == 0 and out_json(cp)["clean"] is True,
            f"rc={cp.returncode}")

        dirty = write(z, "dirty.md", "# Orientation\nreconvene due tic 640\n")
        cp = run(z, "sweep", dirty)
        d = out_json(cp)
        arm("sweep_dirty_exit3_typed",
            cp.returncode == 3
            and d["refusal"] == "volatile_stowaways_undispositioned"
            and d["findings_open"][0]["class"] == "due_marker"
            and "REFUSED" in cp.stderr,
            f"rc={cp.returncode}")

        # ---- arm 3: the LIVED-EVIDENCE shape — stale active_arcs entry caught
        #      as computed_gate_line with suggested STRIP
        z3 = make_zone(tmp, "z3")
        lived = write(z3, "office-lanes-fixture.json", LIVED_FIXTURE)
        cp = run(z3, "sweep", lived)
        d = out_json(cp)
        f0 = d["findings_open"][0] if d["findings_open"] else {}
        arm("lived_cohort_caught_as_computed_gate_line",
            cp.returncode == 3
            and len(d["findings_open"]) == 1
            and f0["class"] == "computed_gate_line"
            and f0["suggested_disposition"] == "strip"
            and LIVED_COHORT_LINE in f0["excerpt"],
            f"rc={cp.returncode} findings={d.get('findings_open')}")

        # ---- arm 4: count_snapshot detection
        z4 = make_zone(tmp, "z4")
        counts = write(z4, "counts.md", "Status: 46 active signals in the manifold.\n")
        cp = run(z4, "sweep", counts)
        d = out_json(cp)
        arm("count_snapshot_detected",
            cp.returncode == 3 and d["findings_open"][0]["class"] == "count_snapshot",
            f"rc={cp.returncode}")

        # ---- arms 5-7: suppressions — already-stamped / provenance / hash lines
        z5 = make_zone(tmp, "z5")
        s1 = write(z5, "stamped.md", "reconvene due tic 640  [last_verified_tic: 631 · ttl_tics: 10]\n")
        s2 = write(z5, "prov.md", "born_tic: 607 and promoted_tic: 611 record history.\n")
        s3 = write(z5, "hash.md", "pin sha256 8ecc3edd due tic 999 (hash line)\n")
        arm("already_stamped_suppressed", run(z5, "sweep", s1).returncode == 0)
        arm("provenance_stamp_suppressed", run(z5, "sweep", s2).returncode == 0)
        arm("hash_line_suppressed", run(z5, "sweep", s3).returncode == 0)

        # ---- arm 8: plain due_marker OUTSIDE a computed container suggests stamp
        z8 = make_zone(tmp, "z8")
        plain = write(z8, "plain.json", '{\n "note": "reconvene due tic 640"\n}\n')
        cp = run(z8, "sweep", plain)
        d = out_json(cp)
        arm("due_marker_outside_container_suggests_stamp",
            cp.returncode == 3 and d["findings_open"][0]["class"] == "due_marker"
            and d["findings_open"][0]["suggested_disposition"] == "stamp",
            f"rc={cp.returncode}")

        # ---- arms 9-10: strip on text -> removed + re-sweep clean + receipt shas
        z9 = make_zone(tmp, "z9")
        t = write(z9, "t.md", "keep me\nreconvene due tic 640\nkeep me too\n")
        fid = out_json(run(z9, "sweep", t))["findings_open"][0]["finding_id"]
        before = sha(t)
        cp = run(z9, "strip", t, "--finding", fid, "--tic", "631")
        rec = out_json(cp)["receipt"]
        arm("strip_text_removes_line",
            cp.returncode == 0 and "due tic 640" not in pathlib.Path(t).read_text(),
            f"rc={cp.returncode}")
        arm("strip_receipt_shas_computed_at_write",
            rec["surface_sha256_before"] == before and rec["surface_sha256_after"] == sha(t)
            and rec["surface_sha256_before"] != rec["surface_sha256_after"])
        arm("strip_then_resweep_clean", run(z9, "sweep", t).returncode == 0)

        # ---- arm 11: strip on JSON keeping validity -> allowed
        z11 = make_zone(tmp, "z11")
        j = write(z11, "arr.json", LIVED_FIXTURE)
        fid = out_json(run(z11, "sweep", j))["findings_open"][0]["finding_id"]
        cp = run(z11, "strip", j, "--finding", fid, "--tic", "631")
        parses = True
        try:
            json.loads(pathlib.Path(j).read_text())
        except json.JSONDecodeError:
            parses = False
        arm("strip_json_valid_result_allowed",
            cp.returncode == 0 and parses and run(z11, "sweep", j).returncode == 0,
            f"rc={cp.returncode} parses={parses}")

        # ---- arm 12: strip on JSON that would corrupt -> typed refusal, untouched
        #      (the volatile line is the LAST member after a comma-bearing
        #      sibling: removing it leaves a trailing comma -> unparseable)
        z12 = make_zone(tmp, "z12")
        j2 = write(z12, "corrupt.json", '{\n "keep": 1,\n "note": "reconvene due tic 640"\n}\n')
        fid = out_json(run(z12, "sweep", j2))["findings_open"][0]["finding_id"]
        before = sha(j2)
        cp = run(z12, "strip", j2, "--finding", fid, "--tic", "631")
        d = out_json(cp)
        arm("strip_json_corrupting_refused_typed_untouched",
            cp.returncode == 3 and d["refusal"] == "strip_would_corrupt_surface"
            and sha(j2) == before and "REFUSED" in cp.stderr,
            f"rc={cp.returncode}")

        # ---- arm 13: stamp on text -> annotated + re-sweep clean
        z13 = make_zone(tmp, "z13")
        t2 = write(z13, "t2.md", "reconvene due tic 640\n")
        fid = out_json(run(z13, "sweep", t2))["findings_open"][0]["finding_id"]
        cp = run(z13, "stamp", t2, "--finding", fid, "--tic", "631", "--ttl-tics", "10")
        arm("stamp_text_annotates_and_resweeps_clean",
            cp.returncode == 0
            and "last_verified_tic: 631" in pathlib.Path(t2).read_text()
            and run(z13, "sweep", t2).returncode == 0,
            f"rc={cp.returncode}")

        # ---- arm 14: stamp on JSON string-value line -> in-string, still parses
        z14 = make_zone(tmp, "z14")
        j3 = write(z14, "s.json", '{\n "note": "reconvene due tic 640"\n}\n')
        fid = out_json(run(z14, "sweep", j3))["findings_open"][0]["finding_id"]
        cp = run(z14, "stamp", j3, "--finding", fid, "--tic", "631")
        parses = True
        try:
            json.loads(pathlib.Path(j3).read_text())
        except json.JSONDecodeError:
            parses = False
        arm("stamp_json_string_value_in_place_parses",
            cp.returncode == 0 and parses and run(z14, "sweep", j3).returncode == 0,
            f"rc={cp.returncode} parses={parses}")

        # ---- arm 15: stamp on JSON non-string line -> typed refusal, untouched
        z15 = make_zone(tmp, "z15")
        j4 = write(z15, "n.json", '{\n "due_tic": 640\n}\n')
        sw = out_json(run(z15, "sweep", j4))
        fid = sw["findings_open"][0]["finding_id"]
        before = sha(j4)
        cp = run(z15, "stamp", j4, "--finding", fid, "--tic", "631")
        d = out_json(cp)
        arm("stamp_json_nonstring_refused_typed_untouched",
            cp.returncode == 3 and d["refusal"] == "stamp_not_derivable_for_surface"
            and sha(j4) == before,
            f"rc={cp.returncode}")

        # ---- arms 16-17: accept -> receipted + visible on re-sweep; missing
        #      --reason is a usage error (exit 2)
        z16 = make_zone(tmp, "z16")
        a = write(z16, "a.md", "Status: 46 active signals.\n")
        fid = out_json(run(z16, "sweep", a))["findings_open"][0]["finding_id"]
        cp_noreason = run(z16, "accept", a, "--finding", fid, "--tic", "631")
        arm("accept_without_reason_usage_exit2", cp_noreason.returncode == 2,
            f"rc={cp_noreason.returncode}")
        cp = run(z16, "accept", a, "--finding", fid, "--tic", "631",
                 "--reason", "narrative count in prose, not a governed baseline value")
        resweep = out_json(run(z16, "sweep", a))
        arm("accept_receipted_and_visible_on_resweep",
            cp.returncode == 0
            and resweep["clean"] is True
            and len(resweep["findings_accepted"]) == 1
            and resweep["findings_accepted"][0]["reason"].startswith("narrative count"),
            f"rc={cp.returncode}")

        # ---- arm 18: a strip/stamp receipt whose mutation did NOT land leaves
        #      the finding OPEN on re-sweep (fail-closed: bytes rule, not receipts)
        z18 = make_zone(tmp, "z18")
        b = write(z18, "b.md", "reconvene due tic 640\n")
        fid = out_json(run(z18, "sweep", b))["findings_open"][0]["finding_id"]
        ledger = os.path.join(z18, "audit-logs/governance/ratify-intake-sweeps/receipts.jsonl")
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"act": "strip", "finding_id": fid,
                                 "surface_base": "b.md", "tic": 631}) + "\n")
        cp = run(z18, "sweep", b)
        arm("phantom_disposition_receipt_stays_open_fail_closed",
            cp.returncode == 3, f"rc={cp.returncode}")

        # ---- arms 19-20: usage/target errors -> exit 2, both verbs
        z19 = make_zone(tmp, "z19")
        arm("sweep_missing_surface_exit2",
            run(z19, "sweep", os.path.join(z19, "nope.md")).returncode == 2)
        c = write(z19, "c.md", "reconvene due tic 640\n")
        arm("strip_bad_finding_id_exit2",
            run(z19, "strip", c, "--finding", "deadbeefdeadbeef", "--tic", "631").returncode == 2)

        # ---- arm 21: REAL-ZONE READ-ONLY leg (real_zone_readonly probe class):
        #      sweep the real office-lanes.json — byte parity asserted; the
        #      sweep verb writes nothing; honest exit reported, never forced
        real = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(SCRIPTS_DIR)))), "..", "audit-logs/boot-injections/worldview/office-lanes.json")
        real = os.path.normpath(os.path.join(SCRIPTS_DIR, "../../../..",
                                             "audit-logs/boot-injections/worldview/office-lanes.json"))
        if os.path.exists(real):
            before = sha(real)
            cp = subprocess.run([sys.executable, SWEEP, "sweep", real],
                                capture_output=True, text=True)
            arm("real_zone_readonly_byte_parity",
                sha(real) == before and cp.returncode in (0, 3),
                f"rc={cp.returncode}")
            results["real_zone_sweep_honest_exit"] = f"exit={cp.returncode} (informational, read-only)"
        else:
            arm("real_zone_readonly_byte_parity", False, f"real surface not found at {real}")

    print(json.dumps(results, indent=1))
    if failures:
        print(f"FAILURES: {failures}", file=sys.stderr)
        return 1
    print(f"ALL {len([k for k in results if results[k] == 'PASS'])} ARMS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
