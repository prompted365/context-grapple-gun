#!/usr/bin/env python3
"""test-continuity-adapter.py — acceptance tests for Primitive 9 (spec §7).

Hermetic: each test builds a temp zone-root sandbox (.ticzone + minimal audit-logs)
and runs continuity-adapter.py against it via --zone-root. The real federation is
never touched. Exit 0 iff all of T-A..T-G pass.

  T-A no hook installed by the adapter (no hook-registration file appears)
  T-B pre receipt does not claim post survival (observed_continuity == null)
  T-C post links prior (previous_receipt_pointer == matching pre receipt_id)
  T-D stop closes without mutation (no governance-state file written)
  T-E receipt failure is fail-soft (exit 0 even when the sink is unwritable)
  T-F duplicate event is idempotent (one receipt for an identical re-fire)
  T-G divergence honesty (changed state -> divergence_status != intact)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ADAPTER = Path(__file__).parent / "continuity-adapter.py"
SINK_REL = "audit-logs/boot-injections/continuity-receipts.jsonl"


def make_sandbox(root: Path, *, roles=None, mandate="task-A"):
    (root / ".ticzone").write_text(json.dumps({"name": "sandbox"}), encoding="utf-8")
    tics = root / "audit-logs" / "tics"
    tics.mkdir(parents=True, exist_ok=True)
    (tics / "t.jsonl").write_text(
        json.dumps({"type": "tic", "count_mode": "counted", "global_counter_after": 364}) + "\n",
        encoding="utf-8")
    ak = root / "autonomous_kernel"
    ak.mkdir(parents=True, exist_ok=True)
    (ak / "actor-registry.json").write_text(json.dumps({"actors": [
        {"entity_id": "ent_homeskillet", "roles": roles or ["interactive_orchestrator", "session_lead"]}
    ]}), encoding="utf-8")
    mdir = root / "audit-logs" / "mogul" / "mandates"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "current.json").write_text(json.dumps({"task": mandate}), encoding="utf-8")
    sdir = root / "audit-logs" / "signals"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "active-manifest.jsonl").write_text("", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# sandbox doctrine\n", encoding="utf-8")


def run(event, zone, payload=None):
    p = subprocess.run(
        [sys.executable, str(ADAPTER), "--event", event, "--zone-root", str(zone)],
        input=json.dumps(payload or {}), capture_output=True, text=True)
    return p


def receipts(zone):
    sink = zone / SINK_REL
    if not sink.is_file():
        return []
    return [json.loads(x) for x in sink.read_text().splitlines() if x.strip()]


results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail and not cond else ''}")


# T-A: adapter installs no hook-registration surface
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    run("compact.pre", z, {"session_id": "s1"})
    installed = list(z.rglob("hooks.json")) + list(z.rglob("settings.json"))
    check("T-A no-install", installed == [], f"unexpected reg files: {installed}")

# T-B: pre does not claim post survival
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    run("PreCompact", z, {"session_id": "s1"})
    r = receipts(z)
    check("T-B pre!=survival",
          len(r) == 1 and r[0]["lifecycle_event"] == "compact.pre" and r[0]["observed_continuity"] is None,
          f"receipts={r}")

# T-C: post links prior pre
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    run("PreCompact", z, {"session_id": "s1"})
    run("PostCompact", z, {"session_id": "s1"})
    r = receipts(z)
    pre = next((x for x in r if x["lifecycle_event"] == "compact.pre"), None)
    post = next((x for x in r if x["lifecycle_event"] == "compact.post"), None)
    check("T-C post-links-prior",
          pre and post and post["previous_receipt_pointer"] == pre["receipt_id"],
          f"pre={pre and pre['receipt_id']} post_ptr={post and post['previous_receipt_pointer']}")

# T-D: stop closes without governance-state mutation
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    mandate = z / "audit-logs/mogul/mandates/current.json"
    manifest = z / "audit-logs/signals/active-manifest.jsonl"
    before = (mandate.read_bytes(), manifest.read_bytes())
    run("Stop", z, {"session_id": "s1"})
    after = (mandate.read_bytes(), manifest.read_bytes())
    r = receipts(z)
    check("T-D stop-no-mutation",
          before == after and len(r) == 1 and r[0]["lifecycle_event"] == "stop",
          f"gov-state changed={before != after} receipts={len(r)}")

# T-E: fail-soft when the sink is unwritable (parent path is a FILE)
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    bi = z / "audit-logs" / "boot-injections"
    # make boot-injections a FILE so mkdir/append raises -> must be caught, exit 0
    if bi.exists():
        import shutil
        shutil.rmtree(bi)
    bi.write_text("blocker", encoding="utf-8")
    p = run("PreCompact", z, {"session_id": "s1"})
    check("T-E fail-soft", p.returncode == 0, f"exit={p.returncode} stderr={p.stderr.strip()[:120]}")

# T-F: duplicate identical event is idempotent
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z)
    run("PreCompact", z, {"session_id": "s1"})
    run("PreCompact", z, {"session_id": "s1"})
    r = [x for x in receipts(z) if x["lifecycle_event"] == "compact.pre"]
    check("T-F idempotent", len(r) == 1, f"pre receipts={len(r)} (expected 1)")

# T-G: divergence honesty — changed active-task -> drifted; changed identity -> broken
with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z, mandate="task-A")
    run("PreCompact", z, {"session_id": "s1"})
    # mutate the active-task surface, then post
    (z / "audit-logs/mogul/mandates/current.json").write_text(json.dumps({"task": "task-B"}), encoding="utf-8")
    run("PostCompact", z, {"session_id": "s1"})
    post = next((x for x in receipts(z) if x["lifecycle_event"] == "compact.post"), None)
    drifted = post and post["divergence_status"] == "drifted"
    check("T-G divergence-drift", bool(drifted), f"divergence={post and post['divergence_status']} (expected drifted)")

with tempfile.TemporaryDirectory() as d:
    z = Path(d)
    make_sandbox(z, roles=["interactive_orchestrator", "session_lead"])
    run("PreCompact", z, {"session_id": "s2"})
    # mutate office identity (roles), then post
    (z / "autonomous_kernel/actor-registry.json").write_text(json.dumps({"actors": [
        {"entity_id": "ent_homeskillet", "roles": ["DIFFERENT_ROLE"]}]}), encoding="utf-8")
    run("PostCompact", z, {"session_id": "s2"})
    post = next((x for x in receipts(z) if x["lifecycle_event"] == "compact.post"), None)
    broken = post and post["divergence_status"] == "broken"
    check("T-G divergence-broken", bool(broken), f"divergence={post and post['divergence_status']} (expected broken)")

print()
passed = sum(1 for _, c, _ in results if c)
total = len(results)
print(f"continuity-adapter acceptance: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
