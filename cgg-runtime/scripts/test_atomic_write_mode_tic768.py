#!/usr/bin/env python3
"""Regression floor for the shared umask-honoring atomic writer.

ROW: bk-atomic-write-mkstemp-replace-drops-mode-to-0600 (standing ruling tic
751; built at /review 768 wave 6, admission B2-wave-6-tic768.json self-sha
fde2800d7566382a).

THE DEFECT: `tempfile.mkstemp()` creates at 0600 by design. A writer that
mkstemp()s a temp and `os.replace()`s it over a destination hands the
destination the TEMP's mode. Every rewrite silently downgrades the artifact to
owner-only. Nothing raises.

WHAT THIS SUITE PROVES, in two layers:

  LAYER 1 — the helper's contract (lib/atomic_write.py): the three mode arms
  (explicit / preserve-existing / umask-derived), the measured return value,
  and the atomicity guarantees.

  LAYER 2 — one arm PER RULED SITE, each named so a failure identifies WHICH
  site regressed. Five of the six are exercised BEHAVIOURALLY against fixture
  destinations (never a live governance surface); the sixth (arena render) is
  exercised behaviourally too, against a fixture copy of the index.

  LAYER 3 — a static no-reintroduction arm over all six files: no
  `tempfile.mkstemp` may return to any of them.

SCOPE HONESTY: every arm here is FIXTURE-GREEN. It proves the writers behave
on temp-directory destinations under this process's umask. It does NOT prove
the live canonical surfaces (audit-logs/signals/active-manifest.jsonl,
FEDERATION-ARENA-INDEX.md, the effective-record index) are correct at their
next real fire, and it does NOT restore any file already downgraded — the
chmod sweep is a SEPARATE later receipted motion, explicitly out of this
increment's scope.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent          # cgg-runtime/scripts
CGG_RUNTIME = HERE.parent                        # cgg-runtime
ZONE_ROOT = CGG_RUNTIME.parents[2]               # canonical/
sys.path.insert(0, str(HERE))

from lib.atomic_write import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    existing_mode,
    umask_default_mode,
)

ARENA_AUDIT = ZONE_ROOT / "audit-logs" / "arenas" / "arena-index-audit.py"
F2_VERIFIER = ZONE_ROOT / "audit-logs" / "f2" / "archetype_shape_verifier.py"
MAPS_AUDIT = ZONE_ROOT / "audit-logs" / "governance" / "maps-freshness-audit.py"
MANIFEST_PRUNE = HERE / "manifest-prune.py"
ATOMIC_APPEND = HERE / "lib" / "atomic_append.py"
EFFECTIVE_RECORD = HERE / "lib" / "effective_record.py"

# The six ruled sites, by file. Layer-3 scans exactly this set.
RULED_SITE_FILES = {
    "site1_arena_index_audit": ARENA_AUDIT,
    "site2_archetype_shape_verifier": F2_VERIFIER,
    "site3_maps_freshness_audit": MAPS_AUDIT,
    "site4_manifest_prune": MANIFEST_PRUNE,
    "site5_lib_atomic_append": ATOMIC_APPEND,
    "site6_lib_effective_record": EFFECTIVE_RECORD,
}


def mode_of(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def load_module(name: str, path: Path):
    """Import a hyphenated / out-of-tree script by file path.

    Bytecode writing is SUPPRESSED for the duration of the load. Three of the
    six ruled sites live under canonical's audit-logs/ tree, and a plain
    importlib load drops a __pycache__/ directory into a governance folder on
    every test run — this suite would otherwise litter the surface it audits.
    (The control gauge is a site too: an instrument that leaves residue in the
    measured directory has contaminated its own measurement.)
    """
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="atomic-write-tic768-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def seed(self, name: str, body: str, mode: int) -> Path:
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        os.chmod(path, mode)
        self.assertEqual(mode_of(path), mode, "fixture seed mode did not take")
        return path


# ---------------------------------------------------------------------------
# LAYER 1 — the helper's contract
# ---------------------------------------------------------------------------
class HelperModePolicy(TempDirCase):
    def test_absent_destination_gets_umask_derived_mode_not_0600(self):
        """New file == what a plain open(path, 'w') would have produced."""
        expected = umask_default_mode()
        target = self.tmp / "new.txt"
        applied = atomic_write_text(target, "hello\n")
        self.assertEqual(mode_of(target), expected)
        self.assertEqual(applied, expected)
        self.assertNotEqual(
            mode_of(target), 0o600,
            "a NEW file created by the shared writer must not be clamped to "
            "0600 — that is the mkstemp default this row exists to remove",
        )
        # Parity with the non-atomic path, measured rather than assumed.
        plain = self.tmp / "plain.txt"
        with open(plain, "w", encoding="utf-8") as handle:
            handle.write("hello\n")
        self.assertEqual(mode_of(target), mode_of(plain))

    def test_existing_destination_keeps_its_mode_across_rewrite(self):
        """THE CURE: a rewrite must not change who can read the file."""
        for seeded in (0o644, 0o640, 0o664, 0o600):
            with self.subTest(seeded=oct(seeded)):
                target = self.seed(f"keep-{seeded:o}.txt", "v1\n", seeded)
                applied = atomic_write_text(target, "v2\n")
                self.assertEqual(mode_of(target), seeded)
                self.assertEqual(applied, seeded)
                self.assertEqual(target.read_text(encoding="utf-8"), "v2\n")

    def test_explicit_mode_wins_over_both_other_arms(self):
        target = self.seed("explicit.txt", "v1\n", 0o644)
        self.assertEqual(atomic_write_text(target, "v2\n", mode=0o600), 0o600)
        self.assertEqual(mode_of(target), 0o600)
        fresh = self.tmp / "explicit-new.txt"
        self.assertEqual(atomic_write_text(fresh, "x\n", mode=0o640), 0o640)
        self.assertEqual(mode_of(fresh), 0o640)

    def test_returned_mode_is_measured_from_the_descriptor(self):
        target = self.seed("measured.txt", "v1\n", 0o640)
        self.assertEqual(atomic_write_text(target, "v2\n"), mode_of(target))
        self.assertEqual(
            atomic_write_bytes(self.tmp / "measured2.bin", b"\x00\x01"),
            umask_default_mode(),
        )

    def test_existing_mode_helper_reports_none_for_absent(self):
        self.assertIsNone(existing_mode(self.tmp / "nope.txt"))
        seeded = self.seed("present.txt", "x\n", 0o640)
        self.assertEqual(existing_mode(seeded), 0o640)


class HelperAtomicity(TempDirCase):
    def test_bytes_roundtrip_and_parents_created(self):
        target = self.tmp / "deep" / "nested" / "out.json"
        atomic_write_bytes(target, b'{"a": 1}\n')
        self.assertEqual(target.read_bytes(), b'{"a": 1}\n')

    def test_failure_leaves_destination_untouched_and_no_temp_residue(self):
        target = self.seed("survivor.txt", "ORIGINAL\n", 0o644)

        class Exploding(bytes):
            pass

        with patch("lib.atomic_write.os.fsync", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "REPLACEMENT\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertEqual(mode_of(target), 0o644)
        residue = [p.name for p in self.tmp.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(residue, [], f"temp residue left behind: {residue}")

    def test_temp_is_created_in_the_destination_directory(self):
        """Same-fs temp — os.replace never crosses a device boundary."""
        seen = {}
        real_open = os.open

        def spy(path, flags, mode=0o777, *a, **k):
            if isinstance(path, str) and path.endswith(".tmp"):
                seen["dir"] = os.path.dirname(path)
            return real_open(path, flags, mode, *a, **k)

        with patch("lib.atomic_write.os.open", side_effect=spy):
            atomic_write_text(self.tmp / "same-fs.txt", "x\n")
        self.assertEqual(seen.get("dir"), str(self.tmp))


# ---------------------------------------------------------------------------
# LAYER 2 — one behavioural arm per ruled site
# ---------------------------------------------------------------------------
class Site1ArenaIndexAudit(TempDirCase):
    """audit-logs/arenas/arena-index-audit.py:374,379 and 618,623."""

    def setUp(self):
        super().setUp()
        self.mod = load_module("w6_arena_index_audit", ARENA_AUDIT)

    def test_manifest_remove_preserves_manifest_mode(self):
        manifest = self.seed(
            "active-manifest.jsonl",
            json.dumps({"signal_id": "sig_keep", "status": "active"}) + "\n"
            + json.dumps({"signal_id": "sig_drop", "status": "active"}) + "\n",
            0o644,
        )
        with patch.object(self.mod, "MANIFEST", str(manifest)):
            removed = self.mod._manifest_remove("sig_drop")
        self.assertEqual(removed, 1)
        self.assertEqual(
            mode_of(manifest), 0o644,
            "arena-index-audit._manifest_remove downgraded the manifest — "
            "site 1a (arena-index-audit.py:374,379) has regressed",
        )
        survivors = [
            json.loads(line)["signal_id"]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(survivors, ["sig_keep"])

    def test_render_preserves_index_mode(self):
        real_index = Path(self.mod.INDEX_MD)
        if not real_index.is_file():
            self.skipTest("FEDERATION-ARENA-INDEX.md absent in this checkout")
        fixture = self.tmp / "FEDERATION-ARENA-INDEX.md"
        shutil.copyfile(real_index, fixture)
        os.chmod(fixture, 0o644)
        args = argparse.Namespace(dry_run=False)
        with patch.object(self.mod, "INDEX_MD", str(fixture)):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    rc = self.mod.cmd_render(args)
        self.assertEqual(rc, 0)
        self.assertEqual(
            mode_of(fixture), 0o644,
            "arena-index-audit render downgraded the index — site 1b "
            "(arena-index-audit.py:618,623) has regressed",
        )
        self.assertTrue(fixture.read_text(encoding="utf-8").strip())


class Site2ArchetypeShapeVerifier(TempDirCase):
    """audit-logs/f2/archetype_shape_verifier.py:416 (shape-variant site).

    mkstemp WITHOUT os.replace: a scratch fixture writer, not a destination
    rewriter. The narrow harm that DID apply is that the fixture landed at
    0600 instead of the umask-derived mode. Migrating while keeping mkstemp
    would have been a no-op cure, so the path allocation moved to mkdtemp +
    absent destinations written through the shared helper.
    """

    def test_self_test_fixtures_are_umask_derived_not_0600(self):
        mod = load_module("w6_archetype_shape_verifier", F2_VERIFIER)
        fixture_dir = self.tmp / "selftest"
        fixture_dir.mkdir()
        with patch("tempfile.mkdtemp", return_value=str(fixture_dir)):
            with patch("shutil.rmtree") as rmtree:
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    rc = mod._self_test()
        self.assertEqual(rc, 0, f"self-test regressed: {out.getvalue()}")
        rmtree.assert_called_once()
        written = sorted(fixture_dir.glob("anchors-*.json"))
        self.assertEqual(
            len(written), 4,
            "expected four synthetic anchor fixtures from _self_test",
        )
        expected = umask_default_mode()
        for path in written:
            self.assertEqual(
                mode_of(path), expected,
                f"{path.name} landed at {oct(mode_of(path))} — site 2 "
                "(archetype_shape_verifier.py:416) has regressed to the "
                "mkstemp 0600 clamp",
            )
            self.assertIn("archetypes", json.loads(path.read_text()))


class Site3MapsFreshnessAudit(TempDirCase):
    """audit-logs/governance/maps-freshness-audit.py:310,316."""

    def test_manifest_remove_preserves_manifest_mode(self):
        mod = load_module("w6_maps_freshness_audit", MAPS_AUDIT)
        manifest = self.seed(
            "active-manifest.jsonl",
            json.dumps({"signal_id": "sig_maps_stale", "status": "active"}) + "\n"
            + json.dumps({"signal_id": "sig_other", "status": "active"}) + "\n",
            0o644,
        )
        paths = {
            "manifest": str(manifest),
            "cgg_scripts": str(HERE),
        }
        removed = mod._manifest_remove(paths, "sig_maps_stale")
        self.assertEqual(removed, 1)
        self.assertEqual(
            mode_of(manifest), 0o644,
            "maps-freshness-audit._manifest_remove downgraded the manifest — "
            "site 3 (maps-freshness-audit.py:310,316) has regressed",
        )
        survivors = [
            json.loads(line)["signal_id"]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(survivors, ["sig_other"])


class Site4ManifestPrune(TempDirCase):
    """cgg-runtime/scripts/manifest-prune.py:431,438 — subprocess, real CLI."""

    def test_prune_preserves_active_manifest_mode(self):
        signals = self.tmp / "audit-logs" / "signals"
        signals.mkdir(parents=True)
        manifest = signals / "active-manifest.jsonl"
        rows = [
            {"signal_id": "sig_live", "status": "active", "volume": 12,
             "tic": 768, "type": "test.row"},
            {"signal_id": "sig_done", "status": "resolved", "volume": 1,
             "tic": 700, "type": "test.row"},
        ]
        manifest.write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )
        os.chmod(manifest, 0o644)
        result = subprocess.run(
            [sys.executable, str(MANIFEST_PRUNE),
             "--zone-root", str(self.tmp), "--quiet"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            mode_of(manifest), 0o644,
            "manifest-prune downgraded active-manifest.jsonl — site 4 "
            f"(manifest-prune.py:431,438) has regressed. stderr={result.stderr}",
        )
        kept = [
            json.loads(line)["signal_id"]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(kept, ["sig_live"])
        residue = [p.name for p in signals.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(residue, [], f"temp residue left behind: {residue}")


class Site5LibAtomicAppend(TempDirCase):
    """cgg-runtime/scripts/lib/atomic_append.py:35 — atomic_write_json."""

    def test_atomic_write_json_preserves_destination_mode(self):
        from lib.atomic_append import atomic_write_json

        target = self.seed("envelope.json", '{"old": true}\n', 0o644)
        atomic_write_json(str(target), {"new": True, "n": 2})
        self.assertEqual(
            mode_of(target), 0o644,
            "atomic_write_json downgraded its destination — site 5 "
            "(lib/atomic_append.py:35) has regressed",
        )
        self.assertEqual(json.loads(target.read_text()), {"new": True, "n": 2})

    def test_atomic_write_json_body_form_is_unchanged(self):
        """indent=2 plus exactly one trailing newline — the pre-migration form."""
        from lib.atomic_append import atomic_write_json

        target = self.tmp / "form.json"
        payload = {"b": 1, "a": [1, 2]}
        atomic_write_json(str(target), payload)
        self.assertEqual(
            target.read_text(encoding="utf-8"), json.dumps(payload, indent=2) + "\n"
        )

    def test_atomic_write_json_new_file_is_not_0600(self):
        from lib.atomic_append import atomic_write_json

        target = self.tmp / "fresh.json"
        atomic_write_json(str(target), {"a": 1})
        self.assertEqual(mode_of(target), umask_default_mode())


class Site6LibEffectiveRecord(TempDirCase):
    """cgg-runtime/scripts/lib/effective_record.py:1032,1038 — _atomic_write."""

    def test_atomic_write_preserves_destination_mode(self):
        from lib.effective_record import _atomic_write

        target = self.seed("effective-record-index.json", "{}\n", 0o644)
        _atomic_write(target, b'{"records": []}\n')
        self.assertEqual(
            mode_of(target), 0o644,
            "effective_record._atomic_write downgraded its destination — "
            "site 6 (lib/effective_record.py:1032,1038) has regressed",
        )
        self.assertEqual(target.read_bytes(), b'{"records": []}\n')

    def test_atomic_write_new_file_is_not_0600(self):
        from lib.effective_record import _atomic_write

        target = self.tmp / "deep" / "effective-record-backrefs.jsonl"
        _atomic_write(target, b"{}\n")
        self.assertEqual(mode_of(target), umask_default_mode())
        self.assertNotEqual(mode_of(target), 0o600)


# ---------------------------------------------------------------------------
# LAYER 3 — no reintroduction, across all six ruled files
# ---------------------------------------------------------------------------
class NoMkstempReintroduction(unittest.TestCase):
    def test_no_ruled_site_calls_tempfile_mkstemp(self):
        for name, path in RULED_SITE_FILES.items():
            with self.subTest(site=name):
                self.assertTrue(path.is_file(), f"{path} missing")
                source = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    "tempfile.mkstemp", source,
                    f"{name} ({path.name}) reintroduced tempfile.mkstemp — "
                    "the 0600 clamp is back on this writer",
                )

    def test_every_ruled_site_routes_through_the_shared_helper(self):
        for name, path in RULED_SITE_FILES.items():
            with self.subTest(site=name):
                source = path.read_text(encoding="utf-8")
                self.assertIn(
                    "atomic_write", source,
                    f"{name} ({path.name}) no longer references the shared "
                    "atomic_write helper",
                )

    def test_helper_is_stdlib_only(self):
        """Parsed with ast, not line-matched.

        A line-prefix scan reads prose out of the module docstring as an
        import statement ("from one created non-atomically." parses as a
        module named `one`). The measured thing is the IMPORT GRAPH, so read
        it from the parse tree.
        """
        source = (HERE / "lib" / "atomic_write.py").read_text(encoding="utf-8")
        stdlib = {"os", "secrets", "stat", "typing", "__future__"}
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    self.fail("the shared helper must not use relative imports")
                found.add((node.module or "").split(".")[0])
        self.assertTrue(found, "no imports parsed — anchor is wrong")
        self.assertLessEqual(
            found, stdlib,
            f"non-stdlib import(s) in the shared helper: {sorted(found - stdlib)}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
