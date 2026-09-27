"""Goal 76 — the two sibling hooks that compose their own plugin root take the gate's
typed-unresolved cure (RULED /review 825 H3, backlog row
bk-gate-plugin-root-sibling-hooks-posttool-microscan-and-session-restore-t825; built tic 827).

The gate took the cure at fd51bcf and its rider named session-restore.sh and
posttool-microscan.sh as NOT cured. Before this increment, with no CLAUDE_PLUGIN_ROOT, no
project-local vendor tree and no $HOME/.claude/cgg-runtime, BOTH hooks composed
"/cgg-runtime/scripts/lib/atomic-append.sh" from an empty root (reproduced under bash -x at
tic 827 before the cure). Now the root is TYPED; nothing is composed from an unresolved one.

POPULATION (declared): each hook is RUN whole under bash -x in a scratch fixture whose
HOME / CLAUDE_PROJECT_DIR / TMPDIR all sit under pytest's tmp_path, so every state path the
hooks derive lies under scratch; the trace read is the hook's OWN expansions. Both hooks exit
fail-soft early in a bare zone, so the sites past the early exit (resolve_script, the two
embedded-Python _libdir lists, EFFECTIVE_RECORD_SCRIPT) are pinned by SOURCE-FORM assertions
plus a function-extraction run of resolve_script — declared as such, not as a live fire.
post-commit-sync.sh is out of population: it composes nothing from CGG_PLUGIN_ROOT (measured:
zero "$CGG_PLUGIN_ROOT/" occurrences), so there is nothing to cure there.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "hooks"
SR = HOOKS / "session-restore.sh"
PM = HOOKS / "posttool-microscan.sh"
PCS = HOOKS / "post-commit-sync.sh"
REPO = HOOKS.parents[1]  # the plugin root that carries cgg-runtime/

# Same discriminator as the gate's test (test_gate_quiet_failures_tic824.py): a composed
# sub-path under a root-anchored "/cgg-runtime/"; the bare "/cgg-runtime" of the -d probe
# has no trailing separator and is not a composition.
_ROOT_ANCHORED = re.compile(r"(?<![\w/.\-])/cgg-runtime/")
STDIN = '{"session_id":"fx","tool_name":"Read","tool_input":{"file_path":"/x"},"tool_response":{}}'


def root_anchored_lines(trace: str) -> list[str]:
    return [ln for ln in trace.splitlines() if _ROOT_ANCHORED.search(ln)]


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.zone = root / "zone"
        self.home = root / "home"
        self.tmpdir = root / "tmpdir"
        for d in (self.zone, self.home, self.tmpdir):
            d.mkdir(parents=True)

    def env(self, plugin_root):
        e = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "CLAUDE_PROJECT_DIR": str(self.zone),
            "TMPDIR": str(self.tmpdir),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if plugin_root is not None:
            e["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        return e

    def preflight(self, env):
        for k in ("HOME", "CLAUDE_PROJECT_DIR", "TMPDIR"):
            assert env[k].startswith(str(self.root) + os.sep), f"PRE-FLIGHT: {k} escapes scratch"
        assert not (self.home / ".claude" / "cgg-runtime").exists()

    def run(self, hook: Path, plugin_root=None) -> subprocess.CompletedProcess:
        env = self.env(plugin_root)
        self.preflight(env)
        return subprocess.run(["bash", "-x", str(hook)], input=STDIN, text=True,
                              capture_output=True, cwd=str(self.zone), env=env, timeout=120)


@pytest.fixture()
def fx(tmp_path):
    return Fixture(tmp_path)


# ---------------------------------------------------------------- the live fires
@pytest.mark.parametrize("hook", [SR, PM], ids=["session-restore", "posttool-microscan"])
def test_unresolvable_root_composes_no_root_anchored_path(fx, hook):
    r = fx.run(hook, plugin_root=None)
    hits = root_anchored_lines(r.stderr)
    assert not hits, "root-anchored paths composed from an unresolved root:\n" + "\n".join(hits)


@pytest.mark.parametrize("hook", [SR, PM], ids=["session-restore", "posttool-microscan"])
def test_unresolvable_root_is_typed_unresolved(fx, hook):
    r = fx.run(hook, plugin_root=None)
    assert "CGG_PLUGIN_ROOT_STATE=unresolved" in r.stderr
    assert "ATOMIC_LIB=''" in r.stderr or "ATOMIC_LIB=\n" in r.stderr or re.search(r"\+ ATOMIC_LIB=$", r.stderr, re.M)


@pytest.mark.parametrize("hook", [SR, PM], ids=["session-restore", "posttool-microscan"])
def test_stale_non_empty_root_is_also_unresolved(fx, hook):
    stale = fx.root / "no-such-plugin-root"
    r = fx.run(hook, plugin_root=stale)
    assert "CGG_PLUGIN_ROOT_STATE=unresolved" in r.stderr
    assert f"{stale}/cgg-runtime/scripts" not in r.stderr


@pytest.mark.parametrize("hook", [SR, PM], ids=["session-restore", "posttool-microscan"])
def test_resolved_root_is_unchanged(fx, hook):
    """NO-REGRESSION on the path that runs in production: the real repo root resolves and
    the compositions are exactly the pre-cure values."""
    r = fx.run(hook, plugin_root=REPO)
    assert "CGG_PLUGIN_ROOT_STATE=resolved" in r.stderr
    assert f"ATOMIC_LIB={REPO}/cgg-runtime/scripts/lib/atomic-append.sh" in r.stderr
    if hook is SR:
        assert f"CGG_SCRIPTS_DIR={REPO}/cgg-runtime/scripts" in r.stderr


@pytest.mark.parametrize("hook", [SR, PM], ids=["session-restore", "posttool-microscan"])
def test_unresolved_root_hook_still_exits_zero_fail_soft(fx, hook):
    assert fx.run(hook, plugin_root=None).returncode == 0


# ---------------------------------------------------------------- sites past the early exit
def test_session_restore_resolve_script_drops_the_plugin_candidate():
    """resolve_script, extracted from the hook and run with an EMPTY scripts dir: it must
    never test "/<name>" and must keep candidate ORDER (zone override, then HOME fallback)."""
    src = SR.read_text(encoding="utf-8")
    m = re.search(r"^resolve_script\(\) \{.*?^\}", src, re.S | re.M)
    assert m, "resolve_script not found"
    script = (
        'ZONE_ROOT="/zone-fx"; CGG_SCRIPTS_DIR=""; HOME="/home-fx"\n' + m.group(0) +
        "\nresolve_script probe-name.py || true\n"
    )
    r = subprocess.run(["bash", "-x", "-c", script], capture_output=True, text=True)
    tested = re.findall(r"\+ '\[' -f (\S+) '\]'", r.stderr)
    assert tested == ["/zone-fx/scripts/probe-name.py", "/home-fx/.claude/cgg-runtime/scripts/probe-name.py"], tested


def test_session_restore_resolve_script_keeps_the_plugin_candidate_when_resolved():
    src = SR.read_text(encoding="utf-8")
    m = re.search(r"^resolve_script\(\) \{.*?^\}", src, re.S | re.M)
    script = (
        'ZONE_ROOT="/zone-fx"; CGG_SCRIPTS_DIR="/plug-fx/cgg-runtime/scripts"; HOME="/home-fx"\n'
        + m.group(0) + "\nresolve_script probe-name.py || true\n"
    )
    r = subprocess.run(["bash", "-x", "-c", script], capture_output=True, text=True)
    tested = re.findall(r"\+ '\[' -f (\S+) '\]'", r.stderr)
    assert tested == ["/zone-fx/scripts/probe-name.py", "/plug-fx/cgg-runtime/scripts/probe-name.py",
                      "/home-fx/.claude/cgg-runtime/scripts/probe-name.py"], tested


def test_session_restore_embedded_python_libdirs_are_guarded():
    """The two heredoc _libdir lists composed '/lib' from an empty scripts dir; each must use
    the guarded form so an unresolved root contributes '' (dropped by the `if _libdir`)."""
    src = SR.read_text(encoding="utf-8")
    guarded = src.count("for _libdir in ['${CGG_SCRIPTS_DIR:+$CGG_SCRIPTS_DIR/lib}'")
    bare = src.count("for _libdir in ['$CGG_SCRIPTS_DIR/lib'")
    assert (guarded, bare) == (2, 0), (guarded, bare)


def test_session_restore_effective_record_script_is_guarded():
    src = SR.read_text(encoding="utf-8")
    assert 'EFFECTIVE_RECORD_SCRIPT="${CGG_SCRIPTS_DIR:+$CGG_SCRIPTS_DIR/effective-record.py}"' in src
    assert 'EFFECTIVE_RECORD_SCRIPT="$CGG_SCRIPTS_DIR/effective-record.py"' not in src


def test_session_restore_seal_candidate_is_gated_on_the_typed_state():
    src = SR.read_text(encoding="utf-8")
    assert '"$CGG_PLUGIN_ROOT/cgg-runtime/hooks/cadence-handoff-seal.py"; do' not in src
    assert '[ "$CGG_PLUGIN_ROOT_STATE" = "resolved" ]' in src


def test_no_remaining_untyped_composition_in_either_hook():
    """Every composition from $CGG_PLUGIN_ROOT in both hooks now sits under the typed
    branch or a :+ guard; the -d probe is the one lawful bare use."""
    for hook in (SR, PM):
        src = hook.read_text(encoding="utf-8")
        for ln in src.splitlines():
            if "$CGG_PLUGIN_ROOT/" in ln and "cgg-runtime\" ]" not in ln:
                stripped = ln.lstrip()
                assert (ln.startswith("  ") or ":+" in ln or "_seal_candidates+=" in stripped
                        or stripped.startswith("#")), f"{hook.name}: untyped composition: {ln}"


def test_post_commit_sync_is_out_of_population():
    src = PCS.read_text(encoding="utf-8")
    assert src.count("$CGG_PLUGIN_ROOT/") == 0


def test_rider_travels_verbatim_in_both_hooks():
    for hook in (SR, PM):
        src = hook.read_text(encoding="utf-8")
        assert "DOES-NOT-SATISFY RIDER (the seat's words): this increment does NOT change any hook verb" in src
        assert "bk-gate-plugin-root-sibling-hooks-posttool-microscan-and-session-restore-t825" in src
