#!/usr/bin/env python3
"""braid-input-builder.py — federation-state -> lattice.braid.input envelope.

CGG-rung outer ring for cable BR4 (braid covenant tic 569, Office of the
Harpoonv2). Sibling of contagion-input-builder.py / harmony-input-builder.py.
READ-ONLY of federation state. Writes ONLY audit-logs/braid/input-tic-N.json.

Assembles the input envelope the kernel braid engine
(autonomous_kernel/lattice_braid.py) consumes (SPEC.md §BR4 schema):

  {"type": "lattice.braid.input", "tic": N,
   "conformation_shape8": [...8D STRUCT_DIMS...],
   "conformation_provenance": {...},
   "conformation_shape_history": [{"tic": n, "shape8": [...]}, ...],
   "economy": {"pointer": {...}, "latest": {...flat fields...},
               "heartbeat_detail": {...detail...}},
   "harmony_current": {...} | null,
   "trust_telemetry": {...} | null}

Plus two ADDITIVE fields (covenant scars, recorded in the BR4 cable receipt):
  "substrate_projection" — the C-OT4 16D->9D physics projection computed HERE
      (reusing contagion-input-builder.physics_projection_block by same-dir
      import) because the kernel must not reach down into CGG scripts; null
      + honest flag when the kernel projection/numpy is unavailable.
  "generated_at" — stamped HERE so the kernel engine stays wall-clock-free
      (it copies this field; observability only).

FAIL-SOFT EVERYWHERE: an absent surface yields null + an honest flag in
"honest_flags"; the builder exits 0 with whatever envelope it could assemble.
Conformation projection REUSES contagion-input-builder.conformation_shape by
import (fence #2: shape, never text) — never reimplemented.
"""
import argparse
import glob
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from zone_root import resolve_zone_root  # noqa: E402
ROOT = resolve_zone_root()

BRAID_DIR = os.path.join(ROOT, "audit-logs", "braid")
CONFORMATION_DIR = os.path.join(ROOT, "audit-logs", "conformations")
ECON_DIR = os.path.join(ROOT, "audit-logs", "economy")
ECON_POINTER = os.path.join(ECON_DIR, "current-pointer.json")
HARMONY_CURRENT = os.path.join(ROOT, "audit-logs", "harmony",
                               "disposition-current.json")
TRUST_LATEST = os.path.join(ROOT, "audit-logs", "trust", "latest.json")

HISTORY_K = 6   # conformation shape history depth (tics)


# ---------------------------------------------------------------------------
# Reuse the contagion builder's conformation projection (dashed filename ->
# importlib seam). The shared STRUCT_DIMS shape space lives there; this
# builder NEVER reimplements the projection.
# ---------------------------------------------------------------------------
def _load_contagion_builder():
    path = os.path.join(HERE, "contagion-input-builder.py")
    spec = importlib.util.spec_from_file_location("contagion_input_builder",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_json(path):
    with open(path) as f:
        return json.load(f)


def _rel(path):
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


def _conformation_files():
    files = glob.glob(os.path.join(CONFORMATION_DIR, "tic-*.json"))

    def tic_of(p):
        b = os.path.basename(p)
        try:
            return int(b.replace("tic-", "").replace(".json", ""))
        except ValueError:
            return -1

    return sorted((f for f in files if tic_of(f) >= 0), key=tic_of)


def build(inherit_tic=None):
    honest_flags = []
    sources = {}

    # --- conformation: current shape + history (via contagion projection) --
    shape8 = provenance = None
    history = []
    conf_tic = None
    cb = None
    try:
        cb = _load_contagion_builder()
    except Exception as e:  # fail-soft: projection engine absent
        honest_flags.append(f"contagion_builder_unavailable:{e}")
    if cb is not None:
        try:
            files = _conformation_files()
            if not files:
                raise FileNotFoundError("no conformation tic-*.json found")
            for f in files[-HISTORY_K:]:
                conf = _read_json(f)
                vec, prov = cb.conformation_shape(conf)
                t = conf.get("tic_count_physical", 0)
                history.append({"tic": t, "shape8": vec})
                shape8, provenance, conf_tic = vec, prov, t
            sources["conformation"] = _rel(files[-1])
            sources["conformation_history_glob"] = _rel(
                os.path.join(CONFORMATION_DIR,
                             f"tic-*.json (last {len(history)})"))
        except Exception as e:
            honest_flags.append(f"conformation_absent:{e}")

    # --- economy: pointer + latest snapshot (flat) + heartbeat detail ------
    pointer = latest = detail = None
    pointer_tic = None
    try:
        pointer = _read_json(ECON_POINTER)
        pointer_tic = pointer.get("tic")
        sources["economy_pointer"] = _rel(ECON_POINTER)
    except Exception as e:
        honest_flags.append(f"economy_pointer_absent:{e}")
    # The economy snapshot keeps the ECONOMY's own clock: the latest lookup is
    # keyed on the POINTER's tic, never the chain's — two clocks, one envelope
    # (bk-braid-tic-clock-inheritance).
    if pointer_tic is not None:
        latest_path = os.path.join(ECON_DIR, f"economy-tic-{pointer_tic}.json")
        try:
            snap = _read_json(latest_path)
            latest = {k: v for k, v in snap.items() if k != "detail"}
            detail = snap.get("detail") or {}
            sources["economy_latest"] = _rel(latest_path)
        except Exception as e:
            honest_flags.append(f"economy_latest_absent:{e}")

    # --- tic resolution (bk-braid-tic-clock-inheritance, /review 684) ------
    # The braid's tic identity was ORDER-DEPENDENT: pointer-primary resolution
    # stamps whatever tic the economy pointer happens to carry when the braid
    # runs, so the lag direction is set by scheduling, not by content. The
    # ratified cure is parent-clock INHERITANCE (the chain passes its resolved
    # tic down) with any pointer divergence declared FIRST-CLASS — never a
    # constant offset, which is wrong on exactly the lag-0 tics (the parent
    # row's ALWAYS clause was struck at /review 684 on that evidence).
    clock_divergence = None
    if inherit_tic is not None:
        tic = inherit_tic
        tic_authority = "inherited_parent_clock"
        if pointer_tic is not None and pointer_tic != inherit_tic:
            clock_divergence = {
                "inherited_tic": inherit_tic,
                "economy_pointer_tic": pointer_tic,
                "conformation_tic": conf_tic,
                "resolved_tic": tic,
                "resolution": tic_authority,
                "note": ("order-dependent two-clock divergence declared "
                         "first-class; never corrected by a constant offset "
                         "(/review 684 — lag direction is set by execution "
                         "order)"),
            }
            honest_flags.append(
                f"clock_divergence_declared:pointer={pointer_tic},"
                f"inherited={inherit_tic}")
    else:
        tic = pointer_tic
        tic_authority = "economy_pointer"
        if tic is None:
            tic = conf_tic
            tic_authority = "conformation_fallback"
            if tic is None:
                tic_authority = "unresolved"
                honest_flags.append("tic_unresolved_no_pointer_no_conformation")
        elif conf_tic is not None and conf_tic != pointer_tic:
            # Legacy standalone path: behavior preserved (pointer primary),
            # but the observable two-authority divergence is DECLARED.
            clock_divergence = {
                "inherited_tic": None,
                "economy_pointer_tic": pointer_tic,
                "conformation_tic": conf_tic,
                "resolved_tic": tic,
                "resolution": tic_authority,
                "note": ("order-dependent two-clock divergence declared "
                         "first-class; never corrected by a constant offset "
                         "(/review 684 — lag direction is set by execution "
                         "order)"),
            }
            honest_flags.append(
                f"clock_divergence_declared:pointer={pointer_tic},"
                f"conformation={conf_tic}")

    # --- harmony + trust pointers (null + flag when absent) ----------------
    harmony = None
    try:
        harmony = _read_json(HARMONY_CURRENT)
        sources["harmony"] = _rel(HARMONY_CURRENT)
    except Exception as e:
        honest_flags.append(f"harmony_current_absent:{e}")
    trust = None
    try:
        trust = _read_json(TRUST_LATEST)
        sources["trust"] = _rel(TRUST_LATEST)
    except Exception as e:
        honest_flags.append(f"trust_telemetry_absent:{e}")

    # --- per-leg freshness (cgg-ledger#emitter-rows-must-match-a-reader-
    # predicate, per-leg freshness ray, /review 736; from
    # cpr_mogul_harmony_invoke_37ac2699f535) ---------------------------------
    # clock_divergence above watches the ECONOMY leg only; an empty
    # honest_flags must mean "all legs checked and current", never "the
    # checked subset agreed". Every payload leg gets a freshness entry here,
    # with the harmony leg's by-design lag-1 DECLARED (harmony-invoke runs
    # the braid at step 0 and writes disposition-current.json at step 3, so
    # the braid structurally cannot see the current tic's disposition) —
    # declaration and alarm are different verbs: only lag > expected flags.
    HARMONY_EXPECTED_LAG = 1
    leg_freshness = {}
    if tic is not None:
        leg_freshness["economy_pointer"] = {
            "leg_tic": pointer_tic,
            "checked_by": "clock_divergence",
            "divergent": clock_divergence is not None,
        }
        leg_freshness["conformation"] = {
            "leg_tic": conf_tic,
            "lag": (tic - conf_tic) if conf_tic is not None else None,
        }
        harmony_tic = harmony.get("tic") if isinstance(harmony, dict) else None
        harmony_lag = (tic - harmony_tic) if harmony_tic is not None else None
        leg_freshness["harmony_current"] = {
            "leg_tic": harmony_tic,
            "lag": harmony_lag,
            "expected_lag": HARMONY_EXPECTED_LAG,
            "by_design_note": ("lag<=1 is the declared scheduled position "
                               "(braid runs pre-harmony-write); only a lag "
                               "beyond expected flags as stale"),
        }
        if harmony_lag is not None and harmony_lag > HARMONY_EXPECTED_LAG:
            honest_flags.append(
                f"harmony_leg_stale:lag={harmony_lag},"
                f"expected<={HARMONY_EXPECTED_LAG}")
        elif harmony is not None and harmony_tic is None:
            honest_flags.append("harmony_leg_tic_unreadable")
    leg_freshness["trust_telemetry"] = {
        "leg_tic": None,
        "not_checkable": "surface carries no tic field (observed_at only); "
                         "freshness structurally uncheckable — declared, "
                         "not silently skipped",
    }
    freshness_checked_legs = [
        k for k, v in leg_freshness.items() if "not_checkable" not in v]

    # --- substrate projection (C-OT4 proxy, computed builder-side) ---------
    substrate_projection = None
    if cb is not None and shape8 is not None:
        try:
            block = cb.physics_projection_block(shape8)
            if block is not None:
                substrate_projection = {
                    "shape9": block["shape9"],
                    "drift_band_9d": block["drift_band_9d"],
                    "instrument": "C-OT4 proxy",
                    "instrument_version": block.get("instrument_version"),
                    "available": True,
                    "note": ("projectable into the spatial substrate "
                             "(elevation/gravity terrain); proxy sig16 from "
                             "8D STRUCT_DIMS per contagion-input-builder"),
                }
                sources["physics_projection"] = (
                    "autonomous_kernel/ot_narrative_physics_projection.py")
            else:
                honest_flags.append(
                    "substrate_projection_unavailable_kernel_or_numpy_absent")
        except Exception as e:
            honest_flags.append(f"substrate_projection_failed:{e}")

    envelope = {
        "type": "lattice.braid.input",
        "tic": tic,
        "tic_authority": tic_authority,
        "clock_divergence": clock_divergence,
        # stamped HERE so the kernel engine stays wall-clock-free.
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "conformation_shape8": shape8,
        "conformation_provenance": provenance,
        "conformation_shape_history": history,
        "economy": {"pointer": pointer, "latest": latest,
                    "heartbeat_detail": detail},
        "harmony_current": harmony,
        "trust_telemetry": trust,
        "substrate_projection": substrate_projection,
        "leg_freshness": leg_freshness,
        "freshness_checked_legs": freshness_checked_legs,
        "honest_flags": honest_flags,
        "_sources": sources,
    }

    os.makedirs(BRAID_DIR, exist_ok=True)
    out_path = os.path.join(BRAID_DIR, f"input-tic-{tic}.json")
    with open(out_path, "w") as f:
        json.dump(envelope, f, indent=2)
    return out_path, honest_flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true",
                    help="print the written input path to stdout")
    ap.add_argument("--inherit-tic", type=int, default=None,
                    help="parent-chain resolved tic (clock inheritance; "
                         "also read from BRAID_INHERIT_TIC env)")
    args = ap.parse_args()
    inherit_tic = args.inherit_tic
    if inherit_tic is None:
        env_tic = os.environ.get("BRAID_INHERIT_TIC", "").strip()
        if env_tic:
            try:
                inherit_tic = int(env_tic)
            except ValueError:
                print(f"braid input builder: ignoring non-integer "
                      f"BRAID_INHERIT_TIC={env_tic!r}", file=sys.stderr)
    try:
        out_path, flags = build(inherit_tic=inherit_tic)
    except Exception as e:  # fail-soft to the last resort: report, exit 0
        print(f"braid input builder failed soft: {e}", file=sys.stderr)
        return 0
    if flags:
        print(f"braid input honest flags: {flags}", file=sys.stderr)
    if args.print:
        print(out_path)
    else:
        print(f"braid input written: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
