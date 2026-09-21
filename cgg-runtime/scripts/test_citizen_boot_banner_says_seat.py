#!/usr/bin/env python3
"""Tests for the recognized-citizen boot BANNER in hooks/subagent-citizen-boot.py — the
/review 822 Round 2 Q1 ruling ("Banner says 'seat'", bk-subagent-banner-says-seat-not-citizen-t822).

THE RULING, verbatim:
  "The SubagentStart banner stops typing standing and says office seat. The compiled badge
   remains the only surface that states standing. Agent type names stay. No seat's standing
   changes."

THE DEFECT UNDER CURE (/review 822 docket F-D, three seats at tic 821): a seat booted under a
banner reading "You are booting as a recognized federation entity" while its compiled worldview
badge read `standing=resident` with an explicit not-a-citizen line. Both statements shipped into
ONE spawn. /review 773 had already ruled the conflict resolves NARROWER — but that rule was doing
work the banner should never have created. The cure removes the predication, not the disclaimer.

Contract teeth:
  1. the banner NAMES the office seat
  2. the banner types NO standing for this seat — structurally: it takes no standing parameter,
     so there is no standing value it could render
  3. the banner still ROUTES the reader to the badge, which stays the only standing surface
  4. the /review 773 hook-vs-grant disclaimer survives verbatim with its citation
  5. cure-revert negative control: the pre-fix sentence is absent from the hook source and the
     seat sentence is present (this arm fails CLEANLY against old bytes, in both directions)
  6. SIBLING SITES UNTOUCHED — the cold-boot notice and the task-scoped-worker frame still state
     their standing. They are NOT in this ruling's fence: neither path delivers a compiled badge,
     and /review 752 D3 expressly ruled the cold notice renders the registry value. These guards
     must pass against OLD bytes too — if one flips, the cure leaked out of its fence.

DOES NOT SATISFY: this increment stops the banner typing standing on the FULL-BOOT path ONLY.
The ruling's second sentence — "The compiled badge remains the only surface that states
standing" — is NOT true system-wide after this landing: render_cold_boot_notice and
TASK_SCOPED_WORKER_FRAME still state a standing, deliberately, because neither path ships a
compiled badge and /review 752 D3 expressly ruled the cold notice must render the registry
value. Handed up unresolved at tic 824; no seat's standing changed.

Run:  python3 -m unittest test_citizen_boot_banner_says_seat
"""
import importlib.util
import inspect
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_HOOK = os.path.join(_HERE, "..", "hooks", "subagent-citizen-boot.py")
_SPEC = importlib.util.spec_from_file_location("subagent_citizen_boot", _HOOK)
hook = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hook)

PRE_FIX_SENTENCE = "You are booting as a recognized federation entity"
SEAT_SENTENCE = "You are booting into your office SEAT"


def _src() -> str:
    with open(_HOOK, encoding="utf-8") as fh:
        return fh.read()


class BannerNamesTheOfficeSeat(unittest.TestCase):
    """BEHAVIORAL arm — calls the extracted pure renderer."""

    def test_banner_names_the_office_seat(self):
        out = hook.render_citizen_banner("ent_harpoon_build_citizen", 824)
        self.assertIn("office SEAT", out)
        self.assertIn(SEAT_SENTENCE, out)

    def test_banner_does_not_type_this_seats_standing(self):
        out = hook.render_citizen_banner("ent_harpoon_build_citizen", 824)
        self.assertNotIn(PRE_FIX_SENTENCE, out)
        self.assertNotIn("recognized federation entity", out)
        # the banner never predicates a standing VALUE for this seat
        for standing in ("citizen", "resident", "guest", "recognized_body",
                         "registered_artifact", "unresolved"):
            self.assertNotIn(f"standing: {standing}", out)
            self.assertNotIn(f"standing={standing}", out)

    def test_banner_routes_standing_to_the_compiled_badge(self):
        out = hook.render_citizen_banner("ent_x", 824)
        self.assertIn("Your STANDING and its boundary are stamped in the worldview below", out)
        self.assertIn("Honor your badge.", out)
        self.assertIn("the compiled worldview badge below is AUTHORITATIVE", out)

    def test_banner_keeps_the_review_773_hook_not_grant_disclaimer(self):
        out = hook.render_citizen_banner("ent_x", 824)
        self.assertIn("The CITIZEN-BOOT banner names the boot HOOK, never a standing grant", out)
        self.assertIn("resolves NARROWER, always. Ruled /review 773 on F-772-W10-7 n=3.", out)

    def test_banner_carries_the_entity_and_tic_coordinates(self):
        out = hook.render_citizen_banner("ent_cpr_stepper", 824)
        self.assertIn("[CITIZEN-BOOT: ent_cpr_stepper]", out)
        self.assertIn("(tic 824)", out)
        self.assertTrue(out.endswith("\n"), "banner must keep its trailing newline: main() "
                                            "concatenates the worldview parts directly onto it")

    def test_banner_text_is_standing_independent(self):
        # STRUCTURAL proof of teeth #2: no standing parameter exists to render.
        params = list(inspect.signature(hook.render_citizen_banner).parameters)
        self.assertEqual(params, ["entity", "tic"])
        # two seats whose REGISTRY standings differ produce text differing only by the entity token
        resident_seat = hook.render_citizen_banner("ent_harpoon_build_citizen", 824)
        citizen_seat = hook.render_citizen_banner("ent_harpoon", 824)
        self.assertEqual(resident_seat.replace("ent_harpoon_build_citizen", "ENT"),
                         citizen_seat.replace("ent_harpoon", "ENT"))


class CureRevertNegativeControl(unittest.TestCase):
    """SOURCE-TEXT arm — the discriminating control; fails cleanly in both directions."""

    def test_pre_fix_standing_sentence_absent_from_hook_source(self):
        self.assertNotIn(PRE_FIX_SENTENCE, _src(),
                         "the banner types standing again — cure reverted")

    def test_hook_source_carries_the_seat_sentence(self):
        self.assertIn(SEAT_SENTENCE, _src())

    def test_main_composes_the_banner_through_the_renderer(self):
        self.assertIn('context = render_citizen_banner(entity, tic) + "\\n".join(parts)', _src())


class SiblingSitesUntouched(unittest.TestCase):
    """FENCE guards — these must pass against OLD bytes too. A flip means the cure leaked."""

    def test_cold_notice_still_states_the_registry_standing(self):
        # /review 752 D3: the cold notice renders the REGISTRY value. No badge ships on this
        # path, so it is the only standing surface there is. Out of this ruling's fence.
        out = hook.render_cold_boot_notice("ent_harpoon_build_citizen", 824, "resident", "spawnA")
        self.assertIn("standing: resident", out)
        self.assertIn("actor-registry value", out)

    def test_task_scoped_worker_frame_still_states_worker_standing(self):
        # A worker receives no office-worldview at all. Out of this ruling's fence.
        self.assertIn("standing: task_scoped_worker", hook.TASK_SCOPED_WORKER_FRAME)

    def test_agent_type_name_and_hook_marker_survive(self):
        # "Agent type names stay" — the marker names the boot HOOK and interpolates the entity.
        src = _src()
        self.assertIn('f"[CITIZEN-BOOT: {entity}]', src)
        self.assertIn("KNOWN_EPHEMERAL_TYPES", src)


if __name__ == "__main__":
    unittest.main()
