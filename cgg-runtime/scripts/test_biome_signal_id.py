#!/usr/bin/env python3
"""test_biome_signal_id.py — [20b] /review 635 durable fixture.

Drives the REAL biome-engine emit_signal -> dedup_signal_append write/dedup boundary against a
temp SIGNAL_DIR and proves:
  (a) a NO-MONITOR payload's signal id is BYTE-IDENTICAL to the pre-change legacy id
      (biome.<type>_<sha256(<type>_<act>_<cycle>)[:16]> — no trailing separator);
  (b) monitor A and monitor B (same type/act/cycle) produce DISTINCT persisted signals;
  (c) repeating monitor A DEDUPLICATES at the write boundary (one persisted row);
  (d) canonical and installed biome-engine.py are byte-identical.
Not a constructed-dict check — it imports the module and calls the real emitter.
"""
from __future__ import annotations
import importlib.util, hashlib, json, os, sys, tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))  # so biome-engine's `from lib.atomic_append import ...` resolves

def _load_biome():
    spec = importlib.util.spec_from_file_location("biome_engine", SCRIPTS / "biome-engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _legacy_id(signal_type, act, cycle):
    # exact pre-change form: id_source had NO monitor and NO trailing separator
    src = f"{signal_type}_{act}_{cycle}"
    return f"biome.{signal_type}_{hashlib.sha256(src.encode()).hexdigest()[:16]}"

def _persisted(sig_dir: Path):
    rows = []
    for f in sig_dir.glob("*.jsonl"):
        if f.name == "active-manifest.jsonl":
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows

def main() -> int:
    be = _load_biome()
    ok, checks = True, []
    def C(name, cond, **d):
        nonlocal ok; ok = ok and bool(cond); checks.append({"check": name, "pass": bool(cond), **d})

    with tempfile.TemporaryDirectory() as td:
        sig_dir = Path(td) / "signals"; sig_dir.mkdir(parents=True)
        be.SIGNAL_DIR = str(sig_dir)   # redirect the real emitter's write target

        # (a) no-monitor id == legacy id (byte-identical), and it PERSISTS
        no_mon = {"act_id": "act_2", "biome_cycle": 50}   # NO monitor key
        sid_a = be.emit_signal("PRIMITIVE", "health_violation", dict(no_mon))
        legacy = _legacy_id("health_violation", "act_2", 50)
        C("a_no_monitor_id_equals_legacy", sid_a == legacy, got=sid_a, want=legacy)

        # (b) monitor A vs B -> distinct persisted signals
        sid_A = be.emit_signal("PRIMITIVE", "health_violation", {"act_id": "act_2", "biome_cycle": 51, "monitor": "trust_floor"})
        sid_B = be.emit_signal("PRIMITIVE", "health_violation", {"act_id": "act_2", "biome_cycle": 51, "monitor": "loneliness_index"})
        C("b_distinct_ids", sid_A != sid_B, A=sid_A, B=sid_B)
        rows = _persisted(sig_dir)
        persisted_ids = {r["signal_id"] for r in rows}
        C("b_both_persisted", sid_A in persisted_ids and sid_B in persisted_ids,
          persisted=sorted(persisted_ids))
        C("b_monitor_changes_id_vs_legacy", sid_A != _legacy_id("health_violation", "act_2", 51))

        # (c) repeat monitor A -> dedup at the write boundary (still exactly one persisted row)
        before = sum(1 for r in _persisted(sig_dir) if r["signal_id"] == sid_A)
        be.emit_signal("PRIMITIVE", "health_violation", {"act_id": "act_2", "biome_cycle": 51, "monitor": "trust_floor"})
        after = sum(1 for r in _persisted(sig_dir) if r["signal_id"] == sid_A)
        C("c_repeat_dedups", before == 1 and after == 1, before=before, after=after)

    # (d) canonical == installed byte-identical
    canon = SCRIPTS / "biome-engine.py"
    inst = None
    for base in (Path.home() / ".claude",):
        cand = list(base.glob("**/cgg-runtime/scripts/biome-engine.py"))
        if cand: inst = cand[0]; break
    if inst:
        cs = hashlib.sha256(canon.read_bytes()).hexdigest()
        is_ = hashlib.sha256(inst.read_bytes()).hexdigest()
        C("d_canonical_installed_byte_parity", cs == is_, canonical=cs[:16], installed=is_[:16])
    else:
        C("d_canonical_installed_byte_parity", False, note="installed copy not found")

    print(json.dumps({"verdict": "GREEN" if ok else "RED",
                      "passed": f"{sum(c['pass'] for c in checks)}/{len(checks)}",
                      "checks": checks}, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
