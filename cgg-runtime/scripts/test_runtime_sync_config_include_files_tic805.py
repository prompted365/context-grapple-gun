#!/usr/bin/env python3
"""Tests for the config target's named `include_files` allowlist in
runtime-sync.py (F-804-D2-2, handed up BLOCKING by the tic-804 pointer-path
build; cured tic 805).

The contract under guard: the config install target is scoped to
*.schema.json, and a non-schema config file an INSTALLED consumer reads is
admitted BY NAME through `include_files` — never by a wider glob. The first
admitted file is handoff-payload-mode.json: the installed seal hook resolves
the payload switch from ~/.claude/cgg-runtime/config/, so an uncarried switch
means a flip in canonical is invisible to the installed runtime.

Both arms per documented conditional (selftest-fixture discipline):
key-present AND key-absent; named-and-present AND named-but-missing-on-disk;
named AND sync-excluded (exclusion wins).

Run:  python3 -m unittest test_runtime_sync_config_include_files_tic805
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_spec = importlib.util.spec_from_file_location(
    "runtime_sync", os.path.join(_HERE, "runtime-sync.py"))
runtime_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runtime_sync)

SWITCH = "handoff-payload-mode.json"


def _config_target(include_files=None):
    spec = {
        "canonical_subdir": "config",
        "installed_subdir": ".claude/cgg-runtime/config",
        "pattern": "*.schema.json",
        "type": "DATA_SCHEMA",
    }
    if include_files is not None:
        spec["include_files"] = include_files
    return {"config": spec}


def _make_plugin_root(tmpdir, files):
    """A fixture plugin root carrying only cgg-runtime/config/<files>."""
    config_dir = os.path.join(tmpdir, "plugin", "cgg-runtime", "config")
    os.makedirs(config_dir)
    for name in files:
        with open(os.path.join(config_dir, name), "w") as f:
            f.write("{}\n")
    return os.path.join(tmpdir, "plugin")


class _PatchedTargets(unittest.TestCase):
    """Swap the module-level manifest projections for one test, restore after."""

    def setUp(self):
        self._targets = runtime_sync.INSTALL_TARGETS
        self._exclude = runtime_sync.SYNC_EXCLUDE
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

    def tearDown(self):
        runtime_sync.INSTALL_TARGETS = self._targets
        runtime_sync.SYNC_EXCLUDE = self._exclude
        self._tmp.cleanup()

    def _names(self, plugin_root):
        return sorted(
            s["name"] for s in runtime_sync.discover_surfaces(plugin_root, self.tmpdir)
        )


class TestIncludeFilesAllowlist(_PatchedTargets):

    def test_named_file_is_discovered_beside_schemas(self):
        root = _make_plugin_root(
            self.tmpdir, ["a.schema.json", SWITCH, "other.json"])
        runtime_sync.INSTALL_TARGETS = _config_target([SWITCH])
        runtime_sync.SYNC_EXCLUDE = set()
        self.assertEqual(
            self._names(root), ["config:a.schema", "config:handoff-payload-mode"])

    def test_absent_key_is_the_pre_tic805_behaviour(self):
        root = _make_plugin_root(
            self.tmpdir, ["a.schema.json", SWITCH, "other.json"])
        runtime_sync.INSTALL_TARGETS = _config_target(None)
        runtime_sync.SYNC_EXCLUDE = set()
        self.assertEqual(self._names(root), ["config:a.schema"])

    def test_unnamed_non_schema_file_is_never_carried(self):
        """The allowlist is by NAME — it never widens to the directory."""
        root = _make_plugin_root(self.tmpdir, [SWITCH, "other.json"])
        runtime_sync.INSTALL_TARGETS = _config_target([SWITCH])
        runtime_sync.SYNC_EXCLUDE = set()
        self.assertNotIn("config:other", self._names(root))

    def test_sync_exclude_wins_over_a_named_entry(self):
        root = _make_plugin_root(self.tmpdir, ["a.schema.json", SWITCH])
        runtime_sync.INSTALL_TARGETS = _config_target([SWITCH])
        runtime_sync.SYNC_EXCLUDE = {"config/" + SWITCH}
        self.assertEqual(self._names(root), ["config:a.schema"])

    def test_named_but_missing_on_disk_mints_no_phantom_surface(self):
        root = _make_plugin_root(self.tmpdir, ["a.schema.json"])
        runtime_sync.INSTALL_TARGETS = _config_target([SWITCH])
        runtime_sync.SYNC_EXCLUDE = set()
        self.assertEqual(self._names(root), ["config:a.schema"])

    def test_installed_path_is_the_consumers_candidate_dir(self):
        """The seal hook's third candidate is ~/.claude/cgg-runtime/config/."""
        root = _make_plugin_root(self.tmpdir, [SWITCH])
        runtime_sync.INSTALL_TARGETS = _config_target([SWITCH])
        runtime_sync.SYNC_EXCLUDE = set()
        surfaces = runtime_sync.discover_surfaces(root, self.tmpdir)
        self.assertEqual(len(surfaces), 1)
        self.assertEqual(
            surfaces[0]["installed"],
            os.path.join(os.path.expanduser("~"), ".claude", "cgg-runtime",
                         "config", SWITCH))


class TestRealManifestCarriesTheSwitch(unittest.TestCase):
    """The shipped manifest + the shipped tree, unpatched."""

    def test_manifest_names_the_switch(self):
        with open(os.path.join(os.path.dirname(_HERE), "sync-manifest.json")) as f:
            manifest = json.load(f)
        self.assertIn(
            SWITCH, manifest["install_targets"]["config"].get("include_files", []))

    def test_real_tree_discovers_the_switch(self):
        plugin_root = os.path.dirname(os.path.dirname(_HERE))
        names = [
            s["name"] for s in runtime_sync.discover_surfaces(plugin_root, plugin_root)
        ]
        self.assertIn("config:handoff-payload-mode", names)
        # The standing-dirty bookkeeping manifest stays canonical-only.
        self.assertNotIn("config:agent-status.manifest", names)


if __name__ == "__main__":
    unittest.main()
