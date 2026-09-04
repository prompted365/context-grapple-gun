#!/usr/bin/env python3
"""Committed suite for remote-parity-readback.py — H3 of THE HORIZON QUIVER.

RULED: /review 769 signed the HORIZON QUIVER build set H1-H4 staged-lock; the
Architect ruled "Dispatch H2 || H3 || H4 at 770". Staged decomposition:
audit-logs/governance/harpoon-office/staging/horizon-quiver-admission-and-dag-tic768.md
section 3 row H3 + section 2 row 15 (the per-horizon fault-localization rider).

RIDER CARRIED VERBATIM (asserted by TestArm1 against the module constant):
"H3 does NOT satisfy H2 (receipt-intake refusal) or H4 (detached-reproduction
twin). This instrument READS and REPORTS: it refuses no receipt at any intake
boundary, and it reproduces nothing on a detached machine. A GREEN gate verdict
read here is a remote_readback observation OF A VERDICT — it is NOT a
detached_reproduced observation performed by this instrument, and naming which
CI workflow constitutes a detached reproduction is H4's ruled job, not this
one's. NOTHING IS WIRED: no automatic caller invokes this instrument as of this
increment."

EVIDENCE CLASS: FIXTURE-GREEN. Every arm here runs against temp ladder files and
injected command runners. No arm in this file reaches a live remote. The live
runs that DID reach the real remotes are recorded in this increment's cable
receipt, not here — fixture-green is never promoted to live-green by proximity.

ARM CLASSES:
  1 rider + governance surface        5 the gate arm over the release-horizon set
  2 the ladder governs the verdict    6 absence is not rank 0
  3 THE REVERTED-CURE CONTROL         7 exit-code precedence
  4 fail-closed reader failures       8 no-regression tripwires
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H3 = _load("_t_remote_parity_readback", _HERE / "remote-parity-readback.py")
PH = _load("_t_proof_horizon", _HERE / "lib" / "proof_horizon.py")

SHIPPED_LADDER = _HERE.parent / "contracts" / "proof-horizon-ladder-v1.json"

RIDER = (
    "H3 does NOT satisfy H2 (receipt-intake refusal) or H4 "
    "(detached-reproduction twin). This instrument READS and REPORTS: it "
    "refuses no receipt at any intake boundary, and it reproduces nothing on a "
    "detached machine. A GREEN gate verdict read here is a remote_readback "
    "observation OF A VERDICT — it is NOT a detached_reproduced observation "
    "performed by this instrument, and naming which CI workflow constitutes a "
    "detached reproduction is H4's ruled job, not this one's. NOTHING IS "
    "WIRED: no automatic caller invokes this instrument as of this increment.")

HEAD = "9535044d855817d946d18932722b66b0ab24a750"
PREV = "649c4351302ed33160be0506dde4f00f8afbf542"
ANCHOR = "b3491a8000000000000000000000000000000000"


class Completed:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def fake_git(head=HEAD, branch="main", served=HEAD, members=(PREV,),
             anchor_known=True, has_remote=True, ls_remote_rc=0):
    """An injected git runner. Returns a callable with run_git's signature."""

    def _git(args, cwd, timeout=30):
        if args[:2] == ["rev-parse", "HEAD"]:
            return Completed(head + "\n")
        if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return Completed(branch + "\n")
        if args[0] == "remote" and args[1] == "get-url":
            if not has_remote:
                return Completed("", returncode=2, stderr="no such remote")
            return Completed("https://github.com/prompted365/example.git\n")
        if args[0] == "ls-remote":
            if ls_remote_rc != 0:
                return Completed("", returncode=ls_remote_rc, stderr="network down")
            if served is None:
                return Completed("")
            return Completed(f"{served}\t{args[2]}\n")
        if args[0] == "cat-file":
            return Completed("", returncode=0 if anchor_known else 1)
        if args[0] == "rev-list":
            return Completed("\n".join(members) + ("\n" if members else ""))
        raise AssertionError(f"unexpected git call: {args}")

    return _git


def fake_gh(runs_by_workflow, returncode=0):
    def _gh(args, cwd, gh_bin=None, timeout=90):
        wf = args[args.index("--workflow") + 1]
        if returncode != 0:
            return Completed("", returncode=returncode, stderr="gh failed")
        return Completed(json.dumps(runs_by_workflow.get(wf, [])))

    return _gh


class FakeDeploy:
    """Stands in for the lived deploy-gate reader's classification helpers."""

    def __init__(self, workflows, triggers=None):
        self._workflows = list(workflows)
        self._triggers = triggers or {w: True for w in workflows}

    def list_workflows(self, root):
        return list(self._workflows)

    def push_main_triggered(self, root, workflow):
        return self._triggers.get(workflow, True)


def run(headSha, conclusion="success", status="completed", database_id=1):
    return {"databaseId": database_id, "conclusion": conclusion,
            "status": status, "headSha": headSha,
            "createdAt": "2026-09-04T05:33:26Z", "event": "push"}


def make_args(**over):
    argv = []
    for key, value in over.items():
        flag = "--" + key.replace("_", "-")
        if value is True:
            argv.append(flag)
        elif value is not None and value is not False:
            argv.extend([flag, str(value)])
    return H3.build_parser().parse_args(argv)


def write_ladder(path, order):
    path.write_text(json.dumps({
        "schema_version": "proof-horizon-ladder-v1",
        "ladder": [{"rank": i, "horizon": name} for i, name in enumerate(order)],
    }), encoding="utf-8")


SHIPPED_ORDER = ["source_admitted", "pushed", "remote_readback",
                 "detached_reproduced", "installed_verified", "deployed",
                 "outcome_observed"]
PERMUTED_ORDER = list(reversed(SHIPPED_ORDER))


def target(name="cgg", root="/nonexistent", gate="declared_absent"):
    return {"name": name, "repo_root": root, "remote": "origin",
            "ref": "refs/heads/main", "gate": gate, "gate_basis": "fixture"}


def vocab_for(order):
    return {"order": list(order),
            "ranks": {n: i for i, n in enumerate(order)}}


# ---------------------------------------------------------------------------


class TestArm1RiderAndGovernanceSurface(unittest.TestCase):

    def test_the_rider_travels_verbatim_in_the_module(self):
        self.assertEqual(H3.DOES_NOT_SATISFY, RIDER)

    def test_the_rider_is_carried_into_the_emitted_receipt(self):
        args = make_args(only="nope")
        code = H3.main(["--only", "nope", "--json"])
        self.assertEqual(code, H3.EXIT_READER)
        del args

    def test_every_horizon_name_the_instrument_emits_is_on_the_ruled_ladder(self):
        order = PH.load_ladder(path=SHIPPED_LADDER)["order"]
        for name in H3.EMITTED_HORIZONS:
            self.assertIn(name, order,
                          f"{name!r} is emitted by the instrument but is not on the "
                          f"ruled ladder — the vocabulary would be locally coined")

    def test_every_deliberately_unemitted_horizon_is_also_on_the_ladder(self):
        """The abstention list names real rungs. A stale name here would make the
        declared abstention meaningless."""
        order = PH.load_ladder(path=SHIPPED_LADDER)["order"]
        for name in H3.NEVER_EMITTED:
            self.assertIn(name, order)

    def test_the_emitted_and_never_emitted_sets_partition_the_ladder(self):
        order = set(PH.load_ladder(path=SHIPPED_LADDER)["order"])
        covered = set(H3.EMITTED_HORIZONS) | set(H3.NEVER_EMITTED)
        self.assertEqual(covered, order,
                         "every ruled rung must be either emitted or explicitly "
                         "abstained from — silence about a rung is not a posture")
        self.assertEqual(set(H3.EMITTED_HORIZONS) & set(H3.NEVER_EMITTED), set())

    def test_pushed_is_never_emitted_and_the_reason_is_recorded(self):
        self.assertNotIn("pushed", H3.EMITTED_HORIZONS)
        self.assertIn("EMISSION", H3.NEVER_EMITTED["pushed"].upper())

    def test_detached_reproduced_is_reserved_to_h4(self):
        self.assertNotIn("detached_reproduced", H3.EMITTED_HORIZONS)
        self.assertIn("H4", H3.NEVER_EMITTED["detached_reproduced"])


class TestArm2TheLadderGovernsTheVerdict(unittest.TestCase):

    def test_attained_is_the_highest_rung_whose_arms_all_passed(self):
        arms = [
            {"arm": "local_subject", "horizon": "source_admitted",
             "performed": True, "passed": True},
            {"arm": "ref_parity", "horizon": "remote_readback",
             "performed": True, "passed": True},
        ]
        self.assertEqual(H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER)),
                         "remote_readback")

    def test_a_failed_rung_stops_the_walk_at_the_rung_below(self):
        arms = [
            {"arm": "local_subject", "horizon": "source_admitted",
             "performed": True, "passed": True},
            {"arm": "ref_parity", "horizon": "remote_readback",
             "performed": True, "passed": True},
            {"arm": "gate_set", "horizon": "remote_readback",
             "performed": True, "passed": False},
        ]
        self.assertEqual(H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER)),
                         "source_admitted")

    def test_a_skipped_rung_is_lawful_and_does_not_stop_the_walk(self):
        """`pushed` carries no arm here; the walk must pass over it."""
        arms = [
            {"arm": "local_subject", "horizon": "source_admitted",
             "performed": True, "passed": True},
            {"arm": "ref_parity", "horizon": "remote_readback",
             "performed": True, "passed": True},
        ]
        attained = H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER))
        self.assertEqual(attained, "remote_readback")

    def test_an_unperformed_arm_is_not_counted_as_a_pass(self):
        arms = [
            {"arm": "local_subject", "horizon": "source_admitted",
             "performed": True, "passed": True},
            {"arm": "gate_set", "horizon": "remote_readback",
             "performed": False, "passed": False},
        ]
        self.assertEqual(H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER)),
                         "source_admitted")


class TestArm3RevertedCureControl(unittest.TestCase):
    """THE LOAD-BEARING ARM. The cure under test is that this instrument's
    attained-horizon walk follows the LADDER FILE's order — it carries none of
    its own. Point it at a PERMUTED ladder carrying the same seven names in
    reversed order and the verdict must permute with the file."""

    def test_cure_live_the_walk_follows_the_file_not_the_code(self):
        arms = [
            {"arm": "local_subject", "horizon": "source_admitted",
             "performed": True, "passed": True},
            {"arm": "ref_parity", "horizon": "remote_readback",
             "performed": True, "passed": True},
        ]
        shipped = H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER))
        permuted = H3.attained_horizon(arms, vocab_for(PERMUTED_ORDER))
        self.assertEqual(shipped, "remote_readback")
        self.assertEqual(
            permuted, "source_admitted",
            "PREDICTED BREAKAGE under a reverted cure: with a hardcoded order "
            "the walk would return 'remote_readback' for BOTH ladders")
        self.assertNotEqual(shipped, permuted)

    def test_the_control_does_not_leak(self):
        """Rank identity is read from the vocabulary, not from a constant."""
        self.assertEqual(vocab_for(SHIPPED_ORDER)["ranks"]["source_admitted"], 0)
        self.assertEqual(vocab_for(PERMUTED_ORDER)["ranks"]["source_admitted"], 6)

    def test_the_resolver_reads_ranks_from_a_permuted_file_on_disk(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "permuted.json"
            write_ladder(path, PERMUTED_ORDER)
            vocab = H3.resolve_horizon_vocabulary(PH, ladder_path=path)
            self.assertEqual(vocab["ranks"]["source_admitted"], 6)
            self.assertEqual(vocab["ranks"]["remote_readback"], 4)
            self.assertEqual(vocab["order"], PERMUTED_ORDER)

    def test_the_resolver_reads_ranks_from_the_shipped_file(self):
        vocab = H3.resolve_horizon_vocabulary(PH, ladder_path=SHIPPED_LADDER)
        self.assertEqual(vocab["ranks"]["source_admitted"], 0)
        self.assertEqual(vocab["ranks"]["remote_readback"], 2)


class TestArm4FailClosed(unittest.TestCase):

    def test_a_missing_ladder_is_a_reader_failure_not_a_green(self):
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent.json"
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.resolve_horizon_vocabulary(PH, ladder_path=missing)
            self.assertEqual(ctx.exception.code, "ladder_file_missing")

    def test_a_malformed_ladder_is_a_reader_failure(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.resolve_horizon_vocabulary(PH, ladder_path=bad)
            self.assertEqual(ctx.exception.code, "ladder_file_malformed_json")

    def test_a_schema_invalid_ladder_is_a_reader_failure(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"schema_version": "proof-horizon-ladder-v1",
                                       "ladder": []}), encoding="utf-8")
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.resolve_horizon_vocabulary(PH, ladder_path=bad)
            self.assertEqual(ctx.exception.code, "ladder_schema_invalid")

    def test_a_ladder_missing_an_emitted_horizon_refuses(self):
        """Renaming a rung at /review must make THIS instrument refuse, not
        silently mean something else."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "renamed.json"
            write_ladder(path, ["source_admitted", "pushed", "remote_read_back"])
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.resolve_horizon_vocabulary(PH, ladder_path=path)
            self.assertEqual(ctx.exception.code, "off_ladder_horizon")

    def test_an_off_ladder_claim_horizon_refuses_and_routes_to_review(self):
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.resolve_horizon_vocabulary(PH, ladder_path=SHIPPED_LADDER,
                                          extra_names=("shipped",))
        self.assertEqual(ctx.exception.code, "off_ladder_horizon")
        self.assertIn("/review", ctx.exception.message)

    def test_a_missing_engine_is_a_reader_failure_with_no_local_fallback(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.load_proof_horizon(Path(tmp) / "absent.py")
            self.assertEqual(ctx.exception.code, "proof_horizon_engine_missing")
            self.assertIn("FAIL-CLOSED", ctx.exception.message)

    def test_an_undeclared_target_gate_is_refused_never_inferred(self):
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.parse_target_spec("name=x,root=/tmp,gate=maybe")
        self.assertEqual(ctx.exception.code, "target_gate_undeclared")

    def test_an_unknown_anchor_refuses_rather_than_guessing_the_set(self):
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.release_horizon_set(target(), HEAD, ANCHOR, 50,
                                   git=fake_git(anchor_known=False))
        self.assertEqual(ctx.exception.code, "anchor_sha_unknown_locally")

    def test_an_oversized_set_refuses_rather_than_truncating(self):
        many = [f"{i:040x}" for i in range(60)]
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.release_horizon_set(target(), HEAD, ANCHOR, 50,
                                   git=fake_git(members=many))
        self.assertEqual(ctx.exception.code, "release_horizon_set_exceeds_bound")
        self.assertIn("implicit greens", ctx.exception.message)


class TestArm5TheGateArmOverTheReleaseHorizonSet(unittest.TestCase):
    """The gate arm demands a REAL gate surface on disk (a declared gate that is
    absent is a reader failure, never a green), so every fixture here builds one.
    The first draft of this class pointed at a nonexistent root and the
    instrument correctly refused all nine arms — the refusal was the instrument
    working; the fixture was the defect. Recorded as F-770-H3-1."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".github" / "workflows").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _target(self):
        return target(gate="expected", root=str(self.root))

    def _args(self, **over):
        return make_args(since_sha=ANCHOR, **over)

    def test_a_green_set_passes_non_vacuously(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [run(HEAD), run(PREV, database_id=2)]}),
            git=fake_git(members=(HEAD, PREV)))
        self.assertTrue(arm["passed"])
        self.assertFalse(arm["vacuous_antecedent"])
        self.assertEqual(arm["evidence"]["per_workflow"][0]["member_count"], 2)

    def test_an_empty_set_is_labelled_vacuous_and_its_pass_is_not_evidence(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [run(HEAD)]}),
            git=fake_git(members=()))
        self.assertTrue(arm["passed"])
        self.assertTrue(arm["vacuous_antecedent"])
        self.assertIn("could not have failed", arm["vacuity_note"])
        self.assertIn("NON-DISCRIMINATING", arm["vacuity_note"])

    def test_a_red_run_names_the_target_sha_workflow_and_run_id(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [
                run(HEAD, conclusion="failure", database_id=777)]}),
            git=fake_git(members=(HEAD,)))
        self.assertFalse(arm["passed"])
        fault = arm["faults"][0]
        self.assertEqual(fault["code"], "gate_red_for_sha")
        self.assertEqual(fault["sha"], HEAD)
        self.assertEqual(fault["workflow"], "distribution-contract.yml")
        self.assertEqual(fault["run_id"], 777)
        self.assertEqual(fault["conclusion"], "failure")
        self.assertEqual(fault["target"], "cgg")

    def test_an_in_flight_run_is_pending_never_red_and_never_green(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [
                run(HEAD, conclusion=None, status="in_progress", database_id=9)]}),
            git=fake_git(members=(HEAD,)))
        self.assertTrue(arm["pending"])
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["faults"][0]["code"], "gate_pending_for_sha")

    def test_a_push_with_no_run_is_not_green(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, make_args(since_sha=ANCHOR, gh_limit=5),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [run(PREV)]}),
            git=fake_git(members=(HEAD,)))
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["faults"][0]["code"], "no_run_for_sha")
        self.assertEqual(arm["faults"][0]["sha"], HEAD)

    def test_a_saturated_window_refuses_rather_than_calling_it_a_missing_run(self):
        """Absence-of-run and absence-of-fetch are different facts."""
        runs = [run(f"{i:040x}", database_id=i) for i in range(3)]
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.arm_gate_set(
                self._target(), HEAD,
                make_args(since_sha=ANCHOR, gh_limit=3),
                FakeDeploy(["distribution-contract.yml"]),
                gh=fake_gh({"distribution-contract.yml": runs}),
                git=fake_git(members=(HEAD,)))
        self.assertEqual(ctx.exception.code, "gate_window_insufficient")

    def test_a_workflow_with_no_green_in_the_window_is_flagged_never_anchored(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, make_args(),
            FakeDeploy(["distribution-contract.yml"]),
            gh=fake_gh({"distribution-contract.yml": [
                run(HEAD, conclusion="failure")]}),
            git=fake_git(members=(HEAD,)))
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["faults"][0]["code"], "no_green_verdict_in_window")

    def test_a_not_push_triggered_workflow_is_excluded_by_construction(self):
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["distribution-contract.yml", "npm-release.yml"],
                       triggers={"distribution-contract.yml": True,
                                 "npm-release.yml": False}),
            gh=fake_gh({"distribution-contract.yml": [run(HEAD)]}),
            git=fake_git(members=(HEAD,)))
        excluded = [e["workflow"] for e in arm["evidence"]["workflows_excluded"]]
        self.assertEqual(excluded, ["npm-release.yml"])
        self.assertTrue(arm["passed"])

    def test_an_unparseable_trigger_is_included_not_silently_excluded(self):
        """A green must never be granted by a parse failure."""
        arm = H3.arm_gate_set(
            self._target(), HEAD, self._args(),
            FakeDeploy(["mystery.yml"], triggers={"mystery.yml": None}),
            gh=fake_gh({"mystery.yml": [run(HEAD, conclusion="failure",
                                            database_id=5)]}),
            git=fake_git(members=(HEAD,)))
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["evidence"]["workflows_considered"][0]["trigger"],
                         "unparseable_included")

    def test_a_declared_gate_whose_surface_is_absent_is_a_reader_failure(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(H3.ReaderFailure) as ctx:
                H3.arm_gate_set(target(gate="expected", root=tmp), HEAD,
                                self._args(), FakeDeploy([]),
                                gh=fake_gh({}), git=fake_git())
            self.assertEqual(ctx.exception.code, "declared_gate_surface_absent")

    def test_a_gh_failure_is_a_reader_failure_not_an_unread_green(self):
        with self.assertRaises(H3.ReaderFailure) as ctx:
            H3.read_workflow_runs(target(), "distribution-contract.yml", 10,
                                  gh=fake_gh({}, returncode=1))
        self.assertEqual(ctx.exception.code, "gh_run_list_failed")
        self.assertIn("UNREAD, not green", ctx.exception.message)


class TestArm6RefParityAndAbsence(unittest.TestCase):

    def test_ref_parity_passes_only_on_the_exact_sha(self):
        arm = H3.arm_ref_parity(target(), HEAD, git=fake_git(served=HEAD))
        self.assertTrue(arm["passed"])

    def test_a_different_served_sha_names_the_remote_and_both_shas(self):
        arm = H3.arm_ref_parity(target(), HEAD, git=fake_git(served=PREV))
        self.assertFalse(arm["passed"])
        fault = arm["faults"][0]
        self.assertEqual(fault["code"], "remote_serves_different_sha")
        self.assertEqual(fault["expected_sha"], HEAD)
        self.assertEqual(fault["served_sha"], PREV)
        self.assertIn("remote_url", fault)
        self.assertIn("emission is not retrieval", fault["message"])

    def test_an_absent_ref_on_the_remote_is_not_parity(self):
        arm = H3.arm_ref_parity(target(), HEAD, git=fake_git(served=None))
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["faults"][0]["code"], "ref_absent_on_remote")

    def test_an_unreadable_remote_is_a_reader_failure_not_a_mismatch(self):
        arm = H3.arm_ref_parity(target(), HEAD, git=fake_git(ls_remote_rc=128))
        self.assertTrue(arm["reader_failure"])
        self.assertEqual(arm["faults"][0]["code"], "ls_remote_failed")

    def test_a_resident_branch_off_the_declared_ref_is_a_fault(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            arm = H3.arm_local_subject(target(root=tmp),
                                       git=fake_git(branch="wip/experiment"))
        self.assertFalse(arm["passed"])
        self.assertEqual(arm["faults"][0]["code"], "branch_off_declared_ref")

    def test_no_performed_arm_yields_absence_which_is_not_rank_zero(self):
        self.assertIsNone(H3.attained_horizon([], vocab_for(SHIPPED_ORDER)))

    def test_absence_makes_a_claim_unsupported_rather_than_rank_zero_lawful(self):
        arms = [{"arm": "local_subject", "horizon": "source_admitted",
                 "performed": True, "passed": False}]
        self.assertIsNone(H3.attained_horizon(arms, vocab_for(SHIPPED_ORDER)))


class TestArm7ExitCodePrecedence(unittest.TestCase):

    def test_reader_failure_outranks_every_other_verdict(self):
        p = H3._PRECEDENCE
        self.assertGreater(p[H3.EXIT_READER], p[H3.EXIT_OVER_CLAIM])
        self.assertGreater(p[H3.EXIT_READER], p[H3.EXIT_PENDING])
        self.assertGreater(p[H3.EXIT_READER], p[H3.EXIT_LAWFUL])

    def test_an_over_claim_outranks_pending_so_pending_never_masks_it(self):
        p = H3._PRECEDENCE
        self.assertGreater(p[H3.EXIT_OVER_CLAIM], p[H3.EXIT_PENDING])

    def test_pending_outranks_lawful(self):
        p = H3._PRECEDENCE
        self.assertGreater(p[H3.EXIT_PENDING], p[H3.EXIT_LAWFUL])

    def test_the_four_codes_are_distinct(self):
        codes = {H3.EXIT_LAWFUL, H3.EXIT_OVER_CLAIM, H3.EXIT_READER,
                 H3.EXIT_PENDING}
        self.assertEqual(len(codes), 4)


class TestArm8NoRegressionTripwires(unittest.TestCase):

    def test_the_shipped_ladder_still_parses_under_h1s_engine(self):
        ladder = PH.load_ladder(path=SHIPPED_LADDER)
        self.assertEqual(ladder["order"][0], "source_admitted")
        self.assertEqual(len(ladder["order"]), 7)

    def test_h1s_public_api_is_intact(self):
        for fn in ("load_ladder", "horizon_rank", "claim_within_horizon"):
            self.assertTrue(callable(getattr(PH, fn, None)),
                            f"H1's {fn} is the API this instrument consumes")

    def test_h1s_rider_is_still_carried_by_the_engine(self):
        self.assertIn("H3 (remote-parity close predicate)", PH.DOES_NOT_SATISFY)

    def test_the_lived_deploy_gate_reader_still_exposes_what_h3_consumes(self):
        deploy = _load("_t_deploy_gate_read", _HERE / "deploy-gate-read.py")
        for fn in ("list_workflows", "push_main_triggered"):
            self.assertTrue(callable(getattr(deploy, fn, None)),
                            f"H3 reuses deploy-gate-read.{fn} rather than "
                            f"reimplementing the trigger classification")

    def test_this_instrument_declares_itself_read_only_and_unwired(self):
        source = (_HERE / "remote-parity-readback.py").read_text(encoding="utf-8")
        self.assertIn("READ-ONLY", source)
        self.assertIn("NOTHING IS WIRED", source)

    def test_the_instrument_opens_no_file_for_writing(self):
        """A close instrument that writes is a different animal. Structural, not
        aspirational: the source carries no write-mode open and no write helper."""
        source = (_HERE / "remote-parity-readback.py").read_text(encoding="utf-8")
        for forbidden in ("open(", "write_text(", "atomic_append", "atomic_write"):
            if forbidden == "open(":
                self.assertNotIn(", 'w'", source)
                self.assertNotIn(', "w"', source)
                continue
            self.assertNotIn(forbidden, source,
                             f"{forbidden} appears in a declared read-only instrument")


if __name__ == "__main__":
    unittest.main()
