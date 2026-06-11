#!/usr/bin/env python3
"""test-standing-cap-coverage.py — full-cell coverage assertion (tic 399).

Exits 1 if any entity standing present in the registry has no injection policy, if any policy
violates the safety invariants (non-citizen MUST be capped + APOPHATIC-bounded; citizen full),
or if any rendered non-citizen carries an act-authorized fragment. This is the durable guard
behind "every (kind × standing × lifecycle) cell hydrates something, authority-scaled" — it
fails loudly the moment a new standing is added to the ontology without a policy.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("owv", HERE / "office-worldview.py")
owv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owv)


def zone_root() -> Path | None:
    for p in [HERE, *HERE.parents]:
        if (p / ".ticzone").is_file():
            return p
    return None


ZR = zone_root()
if ZR is None:
    print("FAIL: no zone root"); sys.exit(2)

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


reg = json.loads((ZR / "autonomous_kernel" / "actor-registry.json").read_text(encoding="utf-8"))
actors = reg.get("actors", reg)
standings = sorted({a.get("standing") for a in actors if isinstance(a, dict) and a.get("standing")})

# 1. every standing present in the registry has an EXPLICIT policy (not just the fail-closed default)
for s in standings:
    check(f"registry standing '{s}' has an explicit STANDING_POLICY entry", s in owv.STANDING_POLICY)

# 2. policy invariants — citizen full; every other standing capped + bounded + valid cap class
for s, pol in owv.STANDING_POLICY.items():
    if s == "citizen":
        check("citizen: no cap, all planes, no boundary",
              pol["cap"] is None and pol["planes"] == owv._ALL_PLANES and not pol["boundary"])
    else:
        check(f"{s}: authority-capped (cap is not None)", pol["cap"] is not None)
        check(f"{s}: carries an APOPHATIC boundary string", bool(pol["boundary"]))
        check(f"{s}: cap names a real pertinence class", pol["cap"] in owv.AUTHORITY_DEFAULTS)

# 3. fail-closed default is the most restrictive (capped + bounded)
check("_DEFAULT_POLICY is fail-closed (capped + bounded)",
      owv._DEFAULT_POLICY["cap"] is not None and bool(owv._DEFAULT_POLICY["boundary"]))

# 4. render one entity per standing → the SAFETY invariant: ZERO act-authorized fragments for
#    any non-citizen; an APOPHATIC boundary present. (compile_fragments already applies the cap.)
sample = {}
for a in actors:
    if isinstance(a, dict) and a.get("standing") and a["standing"] not in sample:
        sample[a["standing"]] = a.get("entity_id")
for s, ent in sorted(sample.items()):
    frags = owv.compile_fragments(ZR, ent, 399)
    acts = [f["id"] for f in frags if f["authority"].get("may_act_from")]
    has_apo = any(f["pertinence"]["class"] == "APOPHATIC" for f in frags)
    if s == "citizen":
        check(f"citizen {ent}: rendered (act-authority permitted)", True)
    else:
        check(f"non-citizen {s} ({ent}): ZERO act-authorized fragments", len(acts) == 0)
        check(f"non-citizen {s} ({ent}): carries APOPHATIC boundary", has_apo)

print()
if failures:
    print(f"{len(failures)} FAILED:", ", ".join(failures))
    sys.exit(1)
print(f"all standing-cap coverage assertions PASS ({len(standings)} registry standings covered)")
sys.exit(0)
