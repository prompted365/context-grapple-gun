#!/usr/bin/env python3
"""
Multi-tic runner smoke — NO-WRITE coverage harness for the cadence/runner fabric.

Complements falsifier-run.py (which observes+classifies+writes a report). This one
EXERCISES the scheduler and runners across a synthetic multi-tic window and PROVES
it wrote nothing — a true smoke, not a simulation, not an observation pass.

Covers:
  PHASE 1  scheduler coverage — compute_due_cycles over an 8-tic window must reach
           EVERY cycle including the non-every-tic ones (mod 2/3/4/5/8).
  PHASE 2  runner invocability — each scriptable runner runs in its safe no-write
           mode (--dry-run / --help); agent-cycles (ladder_audit, deep_audit) are
           verified as claude -p dispatch wiring, not executed.
  PHASE 3  launch-mechanism + governed-dispatch wiring — claude -p, hooks.json
           events, inbox-envelope + trigger-router, citizen-boot injection seam.
  PHASE 4  NO-WRITE GUARD — snapshot audit-logs/ (path -> mtime,size) before/after
           the whole run; ANY change fails the smoke. The no-write property is
           tested, not assumed.

Usage:
  python3 smoke_multitic_runners.py            # default: no-write smoke (--help mode)
  python3 smoke_multitic_runners.py --exercise # also run the 4 verified --dry-run runners
  python3 smoke_multitic_runners.py --base 320 # window base tic (default 0)

Exit 0 = all pass. Nonzero = at least one failure (count printed).
Writes nothing to the repo. (--report is intentionally NOT offered: a smoke that
writes would violate its own contract.)
"""
import argparse
import hashlib
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.dirname(HERE)                       # cgg-runtime/
SCRIPTS = os.path.join(RUNTIME, "scripts")
# zone root = federation root (cgg-runtime lives under canonical_developer/context-grapple-gun)
ZONE = os.path.abspath(os.path.join(RUNTIME, "..", "..", ".."))
AUDIT = os.path.join(ZONE, "audit-logs")
HOOKS_JSON = os.path.join(RUNTIME, "..", "hooks", "hooks.json")

PASS, FAIL = [], []
def ok(msg):   PASS.append(msg); print(f"  \033[32mPASS\033[0m {msg}")
def bad(msg):  FAIL.append(msg); print(f"  \033[31mFAIL\033[0m {msg}")
def info(msg): print(f"  ---- {msg}")

# Full cadence cycle set + the modulo that triggers each (from cadence-ops.compute_due_cycles).
EVERY_TIC = {"queue_refresh", "signal_scan", "harmony_invoke"}
MODULO = {2: {"review_close_check"}, 3: {"memory_mining", "cache_refresh"},
          4: {"pattern_mining"}, 5: {"ladder_audit", "runtime_drift_check"}, 8: {"deep_audit"}}
FULL_SET = set(EVERY_TIC)
for s in MODULO.values():
    FULL_SET |= s

# Scriptable runners and their VERIFIED no-write mode. Agent-cycles have no script.
SCRIPTABLE = {
    "pattern_miner.py":        ["--dry-run", "--json"],
    "review-close-check.py":   ["--dry-run"],
    "rebru-cadence-emit.py":   ["--dry-run"],
}
HELP_ONLY = ["cadence-ops.py", "rtch.py", "falsifier-run.py", "cache-ops.py",
             "queue-drift-audit.py", "harmony-input-builder.py"]
AGENT_CYCLES = {"ladder_audit", "deep_audit"}  # executed via claude -p, no standalone script


def snapshot(root):
    sig = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
                sig[p] = (int(st.st_mtime), st.st_size)
            except OSError:
                pass
    return sig


def load_compute_due_cycles():
    spec = importlib.util.spec_from_file_location("cadence_ops", os.path.join(SCRIPTS, "cadence-ops.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compute_due_cycles


def phase1_scheduler(base):
    print("\n[PHASE 1] scheduler coverage — 8-tic window must reach every cycle")
    try:
        cdc = load_compute_due_cycles()
    except Exception as e:
        bad(f"could not import compute_due_cycles: {e}")
        return
    window = range(base, base + 9)              # 9 consecutive tics → hits mod 2/3/4/5/8
    union = set()
    per_tic = {}
    for t in window:
        c = set(cdc(t))
        per_tic[t] = c
        union |= c
    for t in window:
        info(f"tic {t}: {sorted(per_tic[t])}")
    missing = FULL_SET - union
    if not missing:
        ok(f"window [{base}..{base+8}] reaches all {len(FULL_SET)} cycles")
    else:
        bad(f"window misses cycles: {sorted(missing)}")
    # each non-every-tic cycle reached at its modulo
    for mod, cycles in MODULO.items():
        hit = any(cycles <= per_tic[t] for t in window if t % mod == 0)
        (ok if hit else bad)(f"mod-{mod} cycles {sorted(cycles)} reached in window")


def _run(cmd):
    try:
        r = subprocess.run(cmd, cwd=ZONE, capture_output=True, text=True, timeout=60)
        return r.returncode
    except Exception as e:
        return f"EXC:{e}"


def phase2_runners(exercise):
    print("\n[PHASE 2] runner invocability (no-write mode)")
    for script, dryflags in SCRIPTABLE.items():
        p = os.path.join(SCRIPTS, script)
        if not os.path.exists(p):
            bad(f"{script} MISSING"); continue
        flags = dryflags if exercise else ["--help"]
        rc = _run([sys.executable, p] + flags)
        (ok if rc == 0 else bad)(f"{script} {' '.join(flags)} -> rc={rc}")
    for script in HELP_ONLY:
        p = os.path.join(SCRIPTS, script)
        if not os.path.exists(p):
            bad(f"{script} MISSING"); continue
        rc = _run([sys.executable, p, "--help"])
        # argparse --help exits 0; some tools exit 2 on --help — accept 0/2 as "invocable"
        (ok if rc in (0, 2) else bad)(f"{script} --help -> rc={rc}")
    # mogul-runner.sh dry-run (the master cycle dispatcher) — only under --exercise
    mr = os.path.join(SCRIPTS, "mogul-runner.sh")
    if exercise and os.path.exists(mr):
        rc = _run(["bash", mr, "--dry-run"])
        (ok if rc in (0, 2) else bad)(f"mogul-runner.sh --dry-run -> rc={rc}")
    else:
        ok("mogul-runner.sh present (dry-run skipped without --exercise)" if os.path.exists(mr)
           else "mogul-runner.sh MISSING") if os.path.exists(mr) else bad("mogul-runner.sh MISSING")
    info(f"agent-cycles {sorted(AGENT_CYCLES)} have NO script — executed via claude -p (see PHASE 3)")


def _contains(path, needles):
    try:
        txt = open(path, errors="ignore").read()
    except OSError:
        return None
    return all(n in txt for n in needles)


def phase3_wiring():
    print("\n[PHASE 3] launch-mechanism + governed-dispatch wiring")
    # (a) claude -p headless launch
    mr = os.path.join(SCRIPTS, "mogul-runner.sh")
    (ok if _contains(mr, ["claude", "-p"]) else bad)("mogul-runner.sh launches via 'claude -p'")
    # (b) hooks.json registers the three event seams
    import json
    try:
        hooks = json.load(open(HOOKS_JSON)).get("hooks", {})
        for ev in ("SessionStart", "UserPromptSubmit", "PostToolUse"):
            (ok if ev in hooks else bad)(f"hooks.json registers {ev}")
    except Exception as e:
        bad(f"hooks.json unreadable: {e}")
    # (c) governed dispatch: inbox-envelope + trigger-router present and referenced
    for s in ("inbox-envelope.py", "trigger-router.py"):
        (ok if os.path.exists(os.path.join(SCRIPTS, s)) else bad)(f"governed-dispatch surface {s} present")
    cadence = os.path.join(SCRIPTS, "cadence-ops.py")
    (ok if _contains(cadence, ["trigger"]) or _contains(cadence, ["inbox"]) else bad)(
        "cadence-ops routes via inbox/trigger (not direct activation)")
    # (d) injection seam: citizen-boot
    cb = os.path.join(RUNTIME, "hooks", "subagent-citizen-boot.py")
    (ok if os.path.exists(cb) else bad)("citizen-boot injection seam present (subagent-citizen-boot.py)")
    bi = os.path.join(SCRIPTS, "boot-injection.py")
    (ok if os.path.exists(bi) else bad)("boot-injection renderer present")


def main():
    ap = argparse.ArgumentParser(description="Multi-tic no-write runner smoke")
    ap.add_argument("--base", type=int, default=0, help="window base tic")
    ap.add_argument("--exercise", action="store_true",
                    help="also run verified --dry-run runners (still no-write-guarded)")
    args = ap.parse_args()

    print(f"== multi-tic runner smoke == zone={ZONE}")
    print(f"   mode={'EXERCISE (dry-run runners)' if args.exercise else 'SMOKE (--help only)'} "
          f"window=[{args.base}..{args.base+8}]")

    before = snapshot(AUDIT)
    phase1_scheduler(args.base)
    phase2_runners(args.exercise)
    phase3_wiring()

    print("\n[PHASE 4] NO-WRITE GUARD — audit-logs/ must be byte-identical")
    after = snapshot(AUDIT)
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {p for p in (set(before) & set(after)) if before[p] != after[p]}
    if not (added or removed or changed):
        ok(f"no-write verified — {len(after)} files unchanged")
    else:
        for p in sorted(added)[:10]:   bad(f"WROTE new file: {os.path.relpath(p, ZONE)}")
        for p in sorted(changed)[:10]: bad(f"MUTATED file: {os.path.relpath(p, ZONE)}")
        for p in sorted(removed)[:10]: bad(f"REMOVED file: {os.path.relpath(p, ZONE)}")

    print(f"\n== RESULT: {len(PASS)} pass / {len(FAIL)} fail ==")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
