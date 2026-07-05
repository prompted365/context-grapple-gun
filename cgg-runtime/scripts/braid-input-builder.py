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
ROOT = "/Users/breydentaylor/canonical"

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


def build():
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
    tic = None
    try:
        pointer = _read_json(ECON_POINTER)
        tic = pointer.get("tic")
        sources["economy_pointer"] = _rel(ECON_POINTER)
    except Exception as e:
        honest_flags.append(f"economy_pointer_absent:{e}")
    if tic is not None:
        latest_path = os.path.join(ECON_DIR, f"economy-tic-{tic}.json")
        try:
            snap = _read_json(latest_path)
            latest = {k: v for k, v in snap.items() if k != "detail"}
            detail = snap.get("detail") or {}
            sources["economy_latest"] = _rel(latest_path)
        except Exception as e:
            honest_flags.append(f"economy_latest_absent:{e}")
    if tic is None:
        tic = conf_tic
        if tic is None:
            honest_flags.append("tic_unresolved_no_pointer_no_conformation")

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
    args = ap.parse_args()
    try:
        out_path, flags = build()
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
