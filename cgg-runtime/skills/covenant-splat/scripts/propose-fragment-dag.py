#!/usr/bin/env python3
"""DEPRECATED ALIAS (tic 622) — this script was renamed to lower-covenant-expr.py.

Two reasons, both audit findings:
  1. It is a LOWERER, not a proposer — it deterministically lowers an already-proposed
     CovenantExpr; the morphism PROPOSAL is the agentic interpreter's act (kernel spec §9).
  2. The original implementation deduplicated repeated leaves (self-edge crash) and
     dropped per-fragment choice ancestry — both fixed in the parity-faithful lowerer.

This alias forwards all arguments unchanged. Update callers; the alias will be retired
after the drain lane stabilizes.
"""
import os
import sys

sys.stderr.write("[covenant-splat] propose-fragment-dag.py is a DEPRECATED alias -> "
                 "lower-covenant-expr.py (forwarding)\n")
target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lower-covenant-expr.py")
os.execv(sys.executable, [sys.executable, target] + sys.argv[1:])
