#!/usr/bin/env python3
"""Tests for the DECLARED COLD BOOT notice in hooks/subagent-citizen-boot.py — the
/review 752 D3 correction of F-751-S11 (bk-boot-injection-standing-contradiction-same-spawn)
and the S12 cure (bk-boot-dedup-notice-hardcodes-not-available).

The defect under cure (two injections into ONE spawn disagreed on STANDING, tic 751):
the worldview rendered the actor-registry value (`standing=resident`, ladder ray withheld)
while the cold-boot notice for the same spawn's dedup-suppressed re-fire hard-coded
"recognized federation citizen (standing: citizen)". /review 751 P2-Q3 attributed the
defect to the worldview; the registry read at 752 (standing=resident since t735, zero
registry commits since) falsified that premise, and /review 752 D3 re-attributed it
to THIS notice: the hook's "citizen" is a boot CLASS (every registered entity gets the
full boot), the registry's `standing` is the ontology axis — the notice must render the
registry's value, never the class word.

The S12 half: the notice instructed `boot_read_mode='not_available'` UNCONDITIONALLY —
correct for the empty-spawn_id fallback (a sibling may have consumed the key), FALSE for
a per-spawn-keyed re-fire (the key means THIS spawn already received the brief; its
earlier receipt stands).

Contract teeth:
  1. registry standing rendered verbatim (resident stays resident; citizen stays citizen;
     an unregistered id renders `unresolved`, never fail-open to citizen)
  2. the class word never appears as the standing ("standing: citizen" is absent for a
     resident seat)
  3. keyed re-fire → the earlier receipt STANDS; not_available only if none was emitted
  4. unkeyed fallback → not_available is the honest value (unchanged behaviour)
  5. cure-revert negative control: the pre-fix literal is absent from the hook source
  6. entity_standing reads the registry fail-closed (missing file / missing seat → unresolved)

Run:  python3 -m unittest test_citizen_boot_cold_notice_standing
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_HOOK = os.path.join(_HERE, "..", "hooks", "subagent-citizen-boot.py")
_SPEC = importlib.util.spec_from_file_location("subagent_citizen_boot", _HOOK)
hook = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hook)

PRE_FIX_LITERAL = "recognized federation citizen (standing: citizen)"


class ColdNoticeRendersRegistryStanding(unittest.TestCase):
    def test_resident_seat_renders_resident_never_the_class_word(self):
        out = hook.render_cold_boot_notice("ent_harpoon_build_citizen", 752, "resident", "spawnA")
        self.assertIn("standing: resident", out)
        self.assertNotIn("standing: citizen", out)
        self.assertNotIn(PRE_FIX_LITERAL, out)

    def test_citizen_seat_still_renders_citizen(self):
        out = hook.render_cold_boot_notice("ent_harpoon", 752, "citizen", "spawnB")
        self.assertIn("standing: citizen", out)

    def test_unresolved_standing_is_rendered_not_upgraded(self):
        out = hook.render_cold_boot_notice("ent_ghost", 752, "unresolved", "spawnC")
        self.assertIn("standing: unresolved", out)
        self.assertNotIn("standing: citizen", out)

    def test_notice_names_the_class_vs_axis_distinction(self):
        out = hook.render_cold_boot_notice("ent_x", 752, "resident", "spawnD")
        self.assertIn("boot CLASS", out)
        self.assertIn("actor-registry value", out)


class ColdNoticeReceiptIsConditionalOnTheKey(unittest.TestCase):
    def test_keyed_refire_earlier_receipt_stands(self):
        out = hook.render_cold_boot_notice("ent_x", 752, "resident", "spawnE")
        self.assertIn("ALREADY received this brief", out)
        self.assertIn("STANDS", out)
        self.assertIn("spawnE", out)
        # not_available survives ONLY inside the "if you emitted none" clause
        self.assertIn("If you emitted none, boot_read_mode='not_available'", out)
        self.assertNotIn("is the honest value for this spawn (no per-spawn key", out)

    def test_unkeyed_fallback_keeps_not_available(self):
        out = hook.render_cold_boot_notice("ent_x", 752, "resident", "")
        self.assertIn("boot_read_mode='not_available' is the honest value for this spawn", out)
        self.assertIn("no per-spawn key was shipped", out)
        self.assertNotIn("ALREADY received this brief", out)
        self.assertNotIn("STANDS", out)

    def test_both_arms_keep_the_compensating_read_and_the_cause(self):
        for spawn in ("spawnF", ""):
            out = hook.render_cold_boot_notice("ent_x", 752, "resident", spawn)
            self.assertIn("COMPENSATING READ", out)
            self.assertIn("office-worldview.py render --office ent_x --tic 752", out)
            self.assertIn("CAUSE: boot dedup", out)


class EntityStandingReadsTheRegistryFailClosed(unittest.TestCase):
    def _zone(self, actors):
        d = Path(tempfile.mkdtemp(prefix="cold-notice-"))
        (d / "autonomous_kernel").mkdir()
        (d / "autonomous_kernel" / "actor-registry.json").write_text(
            json.dumps({"actors": actors}), encoding="utf-8")
        return d

    def test_reads_resident_and_citizen_verbatim(self):
        z = self._zone([
            {"entity_id": "ent_harpoon_build_citizen", "standing": "resident"},
            {"entity_id": "ent_harpoon", "standing": "citizen"},
        ])
        self.assertEqual(hook.entity_standing(z, "ent_harpoon_build_citizen"), "resident")
        self.assertEqual(hook.entity_standing(z, "ent_harpoon"), "citizen")

    def test_missing_seat_and_missing_registry_are_unresolved(self):
        z = self._zone([{"entity_id": "ent_other", "standing": "citizen"}])
        self.assertEqual(hook.entity_standing(z, "ent_absent"), "unresolved")
        empty = Path(tempfile.mkdtemp(prefix="cold-notice-noreg-"))
        self.assertEqual(hook.entity_standing(empty, "ent_harpoon"), "unresolved")

    def test_seat_without_standing_field_is_unresolved_not_citizen(self):
        z = self._zone([{"entity_id": "ent_blank"}])
        self.assertEqual(hook.entity_standing(z, "ent_blank"), "unresolved")


class CureRevertNegativeControl(unittest.TestCase):
    def test_pre_fix_literal_absent_from_hook_source(self):
        src = open(_HOOK, encoding="utf-8").read()
        self.assertNotIn(PRE_FIX_LITERAL, src,
                         "the hard-coded class-as-standing literal is back — cure reverted")

    def test_cold_branch_calls_the_renderer_with_the_registry_standing(self):
        src = open(_HOOK, encoding="utf-8").read()
        self.assertIn("standing_axis = entity_standing(zone_root, entity)", src)
        self.assertIn("render_cold_boot_notice(entity, tic, standing_axis, str(agent_id))", src)


if __name__ == "__main__":
    unittest.main()
