#!/usr/bin/env python3
"""ARM (a) — the SAME-FILE INSCRIPTION cure: displayed provenance is DERIVED.

RULED /review 808 (cpr_mogul_ladder_audit_b3a7c12be3d5 -> ledger.md#an-instrument-that-
loads-an-authority-and-names-it-in-prose-owes-the-name-to-the-constant). Ruled cure,
verbatim: "CURE AT THE ROOT: derive displayed provenance FROM the constant, so the next
supersession cannot leave prose behind".

THE DISCRIMINATING TEST is `test_every_displayed_site_follows_the_constant`: the constant
is re-pointed in a fixture and EVERY displayed site must follow it in the same motion.
Hard-coding any site back fails that test — it is the revert control in test form.

The second guard is structural: NO second inscription of the authority's identity may
survive anywhere in the file (the two inline comments and the one docstring name the
CONSTANT, since a comment cannot carry a runtime value).

Every case isolates against a TemporaryDirectory — nothing touches the real zone
(Self-Locating Artifact Test Isolation KI).

Run:  python3 -m unittest test_ladder_audit_derived_concern_provenance_tic809
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET = os.path.join(_HERE, "ladder-audit.py")
_SPEC = importlib.util.spec_from_file_location("ladder_audit", _TARGET)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

# The SUPERSEDED artifact's distinguishing token, in every WRITTEN FORM the ruled
# pre-land check searches. The ruling's corrected gate: search the TOKEN, never the
# filename — on this file's own exhibit the filename search returns ZERO because the
# prose named the authority by PARAPHRASE.
_SUPERSEDED_TOKEN_FORMS = ("tic-467", "tic 467", "tic467", "t467")


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


_LEDGER = """### Test Invariant One

`invariant_id`: `ki_test_one`
`terrain_class`: `queue_and_state`

The body of the test invariant.

<!-- promoted from cpr_test_one -->
"""


def _concern_json(paths):
    return json.dumps({
        "_tic": 999,
        "_status": "fixture",
        "rungs": {
            f"r{i}": {"path": p, "candidate_concerns": ["queue-and-state"],
                      "ranked": [{"lane": "queue-and-state", "score": 5}]}
            for i, p in enumerate(paths)
        },
    })


class _Zone:
    """A fixture zone whose concern-source constant can be re-pointed at will."""

    def __init__(self, stack, sourced=(".",)):
        self.tmp = tempfile.TemporaryDirectory()
        stack.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        _write(self.root, ".ticzone", json.dumps({"name": "fixture-zone"}))
        _write(self.root, "audit-logs/governance/constitution-ledger/ledger.md", _LEDGER)
        # Two differently-named derives with IDENTICAL content: re-pointing the constant
        # between them changes ONLY the identity, so any site that fails to follow is
        # carrying a second, hand-typed inscription.
        for tic in ("999", "555"):
            _write(self.root,
                   f"audit-logs/governance/c9-rung-concerns-derived-tic{tic}.json",
                   _concern_json(sourced))

    def rel(self, tic):
        return os.path.join("governance", f"c9-rung-concerns-derived-tic{tic}.json")


class TestLabelDerivation(unittest.TestCase):
    """The helper itself: derives from the constant, never invents."""

    def test_label_derives_the_tic_from_the_constant(self):
        self.assertEqual(
            la._derive_concern_source_label(
                os.path.join("governance", "c9-rung-concerns-derived-tic490.json")),
            "tic-490")

    def test_label_follows_a_re_pointed_constant(self):
        with mock.patch.object(la, "DEFAULT_CONCERN_SOURCE_REL",
                               os.path.join("governance", "c9-x-tic777.json")):
            self.assertEqual(la._derive_concern_source_label(), "tic-777")

    def test_no_tic_token_yields_the_basename_never_an_invention(self):
        # honest-empty: a constant carrying no tic token is labelled by its own basename,
        # never by a remembered/guessed identity.
        self.assertEqual(
            la._derive_concern_source_label(os.path.join("governance", "concerns.json")),
            "concerns.json")

    def test_default_label_tracks_the_live_constant(self):
        self.assertEqual(la._derive_concern_source_label(),
                         la._derive_concern_source_label(la.DEFAULT_CONCERN_SOURCE_REL))


class TestNoSecondInscription(unittest.TestCase):
    """Structural: the authority's identity is inscribed ONCE — in the constant."""

    def setUp(self):
        with io.open(_TARGET, encoding="utf-8") as fh:
            self.src = fh.read()

    def test_superseded_token_absent_in_every_written_form(self):
        for form in _SUPERSEDED_TOKEN_FORMS:
            self.assertEqual(self.src.count(form), 0,
                             f"superseded provenance token still inscribed as {form!r}")

    def test_superseded_filename_absent(self):
        self.assertEqual(self.src.count("c9-rung-concerns-derived-tic467.json"), 0)

    def test_current_identity_inscribed_only_in_the_constant(self):
        """The successor's digits appear ONLY in the constant's own line. (A same-file
        historical reference to a different referent — 'the tic-490 inline pass', a past
        campaign — is NOT a provenance inscription of this authority and is deliberately
        not swept; it is excluded by matching the FILENAME, not the bare digits.)"""
        hits = [ln for ln in self.src.split("\n")
                if "c9-rung-concerns-derived-tic" in ln]
        self.assertEqual(len(hits), 1, f"expected exactly one inscription, got {hits}")
        self.assertIn("DEFAULT_CONCERN_SOURCE_REL", self.src.split(
            "c9-rung-concerns-derived-tic")[0][-200:])


class TestEveryDisplayedSiteDerives(unittest.TestCase):
    """THE DISCRIMINATING TEST. Re-point the constant; every displayed site must follow."""

    def setUp(self):
        self.zone = _Zone(self)

    def _render_all_sites(self, tic):
        """Collect the text of EVERY displayed provenance site, with the constant
        re-pointed at the tic<N> derive."""
        rel = self.zone.rel(tic)
        with mock.patch.object(la, "DEFAULT_CONCERN_SOURCE_REL", rel):
            sel = la.select_kis_per_rung(self.zone.root)
            sites = {
                "scope_declaration": sel["scope_declaration"],
                "format_select_kis": la.format_select_kis(sel),
                "selection_note": la._downaudit_target(
                    {"invariant_id": "ki_test_one", "name": "n", "terrain_class": "t",
                     "lanes": [], "target_rung": "", "body": "", "body_truncated": False},
                    None)["selection_note"],
            }
            pkt = la.build_downaudit_packet(self.zone.root, ".")
            sites["concern_source_caveat"] = (
                pkt["scope_declaration_envelope"]["prefilled_by_assembler"]
                ["concern_source_caveat"])
            # the unsourced-rung `note` needs an ACTIVE rung absent from the source
            unsourced = la.select_kis_per_rung(
                self.zone.root,
                concern_source=os.path.join(self.zone.root, "audit-logs", "governance",
                                            "empty.json"))
            sites["unsourced_note"] = json.dumps(unsourced["rungs"])
        return sites

    def test_every_displayed_site_follows_the_constant(self):
        _write(self.zone.root, "audit-logs/governance/empty.json",
               json.dumps({"rungs": {}}))
        for tic in ("999", "555"):
            sites = self._render_all_sites(tic)
            want, unwanted = f"tic-{tic}", f"tic-{'555' if tic == '999' else '999'}"
            for name, text in sites.items():
                self.assertIn(want, text,
                              f"site {name!r} did not follow the constant to {want}")
                self.assertNotIn(unwanted, text,
                                 f"site {name!r} carries a hand-typed {unwanted}")

    def test_packet_ok_so_the_caveat_site_is_really_exercised(self):
        """Guard against a vacuous pass: the Stage-2 packet must actually assemble,
        or `concern_source_caveat` would never be reached."""
        with mock.patch.object(la, "DEFAULT_CONCERN_SOURCE_REL", self.zone.rel("999")):
            pkt = la.build_downaudit_packet(self.zone.root, ".")
        self.assertTrue(pkt.get("ok"), pkt.get("error"))


class TestCliHelpDerives(unittest.TestCase):
    """The CLI --help surface ships to consumers too — it must derive, executed live."""

    def test_select_kis_help_carries_the_derived_label(self):
        out = subprocess.run(
            [sys.executable, _TARGET, "select-kis", "--help"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(la._derive_concern_source_label(), out.stdout)
        for form in _SUPERSEDED_TOKEN_FORMS:
            self.assertNotIn(form, out.stdout)


if __name__ == "__main__":
    unittest.main()
