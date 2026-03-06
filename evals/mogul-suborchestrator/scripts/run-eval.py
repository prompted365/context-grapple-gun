#!/usr/bin/env python3
"""Run Mogul suborchestrator evaluation suite.

For each scenario x config (old_skill, with_skill):
1. Copy fixture workspace to isolated temp directory
2. Snapshot pre-state
3. Spawn `claude -p` with scenario prompt and agent instructions
4. Snapshot post-state
5. Grade programmatic assertions
6. Save results

Usage:
    python3 run-eval.py --iteration 1
    python3 run-eval.py --iteration 1 --scenario queue_refresh --config with_skill
    python3 run-eval.py --dry-run
    python3 run-eval.py --help

Exit codes:
    0 - All runs completed (some assertions may have failed)
    1 - Invalid arguments
    2 - Infrastructure failure (missing tools, broken fixtures)
    3 - All runs failed
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = EVAL_ROOT / "scripts"
EVALS_CONFIG = EVAL_ROOT / "evals.json"

# Map scenario IDs to iteration output directory names
SCENARIO_TO_DIR = {
    "queue_refresh": "eval-queue-refresh",
    "enrichment_advance": "eval-enrichment-advance",
    "dual_cycle": "eval-orchestration-mode",
}

CONFIGS = ["old_skill", "with_skill"]


def load_evals_config() -> dict:
    with open(EVALS_CONFIG) as f:
        return json.load(f)


def resolve_agent_prompt(config: str, eval_config: dict) -> str:
    """Load the agent prompt for the given config variant."""
    if config == "old_skill":
        prompt_path = EVAL_ROOT / eval_config["baseline_skill"]
    else:
        prompt_path = EVAL_ROOT / eval_config["current_skill"]

    if not prompt_path.exists():
        raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")

    text = prompt_path.read_text()
    # Strip YAML frontmatter if present (agent prompt files have it)
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip("\n")
    return text


def copy_fixture(fixture_dir: Path, dest: Path) -> None:
    """Copy fixture workspace to an isolated temp directory."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(fixture_dir, dest)


def run_snapshot(workspace: Path, output: Path) -> dict:
    """Run snapshot-state.py and return parsed result."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "snapshot-state.py"),
            "--workspace-dir", str(workspace),
            "--output", str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Snapshot failed (exit {result.returncode}): {result.stderr}")

    with open(output) as f:
        return json.load(f)


def run_grading(pre_path: Path, post_path: Path, scenario: str, output: Path) -> dict:
    """Run grade-governance.py and return parsed result."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "grade-governance.py"),
            "--pre", str(pre_path),
            "--post", str(post_path),
            "--eval-config", str(EVALS_CONFIG),
            "--scenario", scenario,
            "--output", str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # grade-governance returns 1 on assertion failures (not a crash)
    if result.returncode > 1:
        raise RuntimeError(f"Grading failed (exit {result.returncode}): {result.stderr}")

    with open(output) as f:
        return json.load(f)


def spawn_claude(
    agent_prompt: str,
    scenario_prompt: str,
    workspace: Path,
    tools: list[str],
    model: str,
    max_turns: int,
) -> dict:
    """Spawn a headless claude -p process in the workspace directory.

    Returns dict with stdout, stderr, returncode, and duration_s.
    """
    # Compose the full prompt: agent instructions + scenario prompt
    full_prompt = (
        f"# Agent Instructions\n\n{agent_prompt}\n\n"
        f"# Task\n\n{scenario_prompt}"
    )

    cmd = [
        "claude",
        "-p", full_prompt,
        "--model", model,
        "--max-turns", str(max_turns),
        "--allowedTools", ",".join(tools),
        "--output-format", "json",
    ]

    start = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(workspace),
            timeout=300,  # 5 min per run
        )
    except subprocess.TimeoutExpired:
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        return {
            "stdout": "",
            "stderr": "TIMEOUT after 300s",
            "returncode": -1,
            "duration_s": duration,
            "timed_out": True,
        }

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "duration_s": duration,
        "timed_out": False,
    }


def run_single_eval(
    scenario_id: str,
    config: str,
    test_case: dict,
    eval_config: dict,
    iteration_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Run a single scenario x config eval. Returns result dict."""
    eval_dir_name = SCENARIO_TO_DIR.get(scenario_id, f"eval-{scenario_id}")
    output_dir = iteration_dir / eval_dir_name / config / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    fixture_dir = EVAL_ROOT / test_case["fixture_dir"]
    if not fixture_dir.exists():
        return {
            "scenario": scenario_id,
            "config": config,
            "status": "error",
            "error": f"Fixture dir not found: {fixture_dir}",
        }

    # Load agent prompt
    try:
        agent_prompt = resolve_agent_prompt(config, eval_config)
    except FileNotFoundError as e:
        return {
            "scenario": scenario_id,
            "config": config,
            "status": "error",
            "error": str(e),
        }

    if dry_run:
        return {
            "scenario": scenario_id,
            "config": config,
            "status": "dry_run",
            "fixture_dir": str(fixture_dir),
            "output_dir": str(output_dir),
            "agent_prompt_lines": len(agent_prompt.splitlines()),
            "scenario_prompt_preview": test_case["prompt"][:120] + "...",
        }

    # Create isolated workspace in temp dir
    with tempfile.TemporaryDirectory(prefix=f"mogul-eval-{scenario_id}-{config}-") as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        copy_fixture(fixture_dir, workspace)

        # Pre-snapshot
        pre_path = output_dir / "snapshot-pre.json"
        try:
            pre_snapshot = run_snapshot(workspace, pre_path)
        except RuntimeError as e:
            return {
                "scenario": scenario_id,
                "config": config,
                "status": "error",
                "error": f"Pre-snapshot failed: {e}",
            }

        # Spawn claude -p
        tools = eval_config.get("tools", ["Read", "Grep", "Glob", "Bash", "Write", "Edit"])
        model = eval_config.get("model", "sonnet")
        max_turns = eval_config.get("max_turns", 20)

        claude_result = spawn_claude(
            agent_prompt=agent_prompt,
            scenario_prompt=test_case["prompt"],
            workspace=workspace,
            tools=tools,
            model=model,
            max_turns=max_turns,
        )

        # Save claude output
        claude_output_path = output_dir / "claude-output.json"
        with open(claude_output_path, "w") as f:
            json.dump(claude_result, f, indent=2)
            f.write("\n")

        # Parse claude response if JSON
        claude_response = None
        if claude_result["stdout"]:
            try:
                claude_response = json.loads(claude_result["stdout"])
            except json.JSONDecodeError:
                claude_response = {"raw": claude_result["stdout"][:2000]}

        # Post-snapshot
        post_path = output_dir / "snapshot-post.json"
        try:
            post_snapshot = run_snapshot(workspace, post_path)
        except RuntimeError as e:
            return {
                "scenario": scenario_id,
                "config": config,
                "status": "error",
                "error": f"Post-snapshot failed: {e}",
                "claude_result": {
                    "returncode": claude_result["returncode"],
                    "duration_s": claude_result["duration_s"],
                    "timed_out": claude_result.get("timed_out", False),
                },
            }

        # Grade programmatic assertions
        grading_path = output_dir / "grading.json"
        try:
            grading = run_grading(pre_path, post_path, scenario_id, grading_path)
        except RuntimeError as e:
            return {
                "scenario": scenario_id,
                "config": config,
                "status": "error",
                "error": f"Grading failed: {e}",
                "claude_result": {
                    "returncode": claude_result["returncode"],
                    "duration_s": claude_result["duration_s"],
                    "timed_out": claude_result.get("timed_out", False),
                },
            }

        # Copy workspace state for inspection
        workspace_archive = output_dir / "workspace-post"
        if workspace_archive.exists():
            shutil.rmtree(workspace_archive)
        shutil.copytree(workspace, workspace_archive)

    return {
        "scenario": scenario_id,
        "config": config,
        "status": "completed",
        "claude_result": {
            "returncode": claude_result["returncode"],
            "duration_s": claude_result["duration_s"],
            "timed_out": claude_result.get("timed_out", False),
        },
        "grading": {
            "all_passed": grading.get("all_passed", False),
            "passed": grading.get("passed", 0),
            "failed": grading.get("failed", 0),
            "total": grading.get("total_assertions", 0),
            "pass_rate": grading.get("pass_rate", 0),
            "llm_judged_pending": grading.get("llm_judged_pending", []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Mogul suborchestrator evaluation suite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--iteration", type=int, default=1,
        help="Iteration number (default: 1)",
    )
    parser.add_argument(
        "--scenario",
        choices=["queue_refresh", "enrichment_advance", "dual_cycle"],
        help="Run only this scenario (default: all)",
    )
    parser.add_argument(
        "--config",
        choices=CONFIGS,
        help="Run only this config variant (default: both)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without executing",
    )
    parser.add_argument(
        "--output", default=None,
        help="Path for benchmark.json (default: iteration-N/benchmark.json)",
    )
    args = parser.parse_args()

    # Validate claude CLI
    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(json.dumps({"error": "claude CLI not found or unresponsive"}), file=sys.stderr)
        return 2

    eval_config = load_evals_config()
    test_cases = {tc["id"]: tc for tc in eval_config.get("test_cases", [])}
    iteration_dir = EVAL_ROOT / f"iteration-{args.iteration}"

    # Determine which runs to execute
    scenarios = [args.scenario] if args.scenario else list(test_cases.keys())
    configs = [args.config] if args.config else CONFIGS

    results = []
    for scenario_id in scenarios:
        tc = test_cases.get(scenario_id)
        if not tc:
            print(f"WARNING: scenario '{scenario_id}' not found in evals.json", file=sys.stderr)
            continue

        for config in configs:
            label = f"{scenario_id}/{config}"
            if not args.dry_run:
                print(f"[RUN] {label}", file=sys.stderr)

            result = run_single_eval(
                scenario_id=scenario_id,
                config=config,
                test_case=tc,
                eval_config=eval_config,
                iteration_dir=iteration_dir,
                dry_run=args.dry_run,
            )
            results.append(result)

            if not args.dry_run:
                status = result.get("status", "unknown")
                if status == "completed":
                    g = result.get("grading", {})
                    print(
                        f"[DONE] {label}: {g.get('passed', 0)}/{g.get('total', 0)} passed "
                        f"({result['claude_result']['duration_s']:.1f}s)",
                        file=sys.stderr,
                    )
                else:
                    print(f"[{status.upper()}] {label}: {result.get('error', '')}", file=sys.stderr)

    # Build benchmark summary
    completed = [r for r in results if r.get("status") == "completed"]
    benchmark = {
        "eval_suite": eval_config.get("eval_suite", "mogul-suborchestrator"),
        "iteration": args.iteration,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(results),
        "completed": len(completed),
        "errors": len(results) - len(completed),
        "summary": {},
        "runs": results,
    }

    # Per-config summary
    for config in configs:
        config_runs = [r for r in completed if r.get("config") == config]
        if config_runs:
            total_passed = sum(r["grading"]["passed"] for r in config_runs)
            total_assertions = sum(r["grading"]["total"] for r in config_runs)
            benchmark["summary"][config] = {
                "runs": len(config_runs),
                "total_passed": total_passed,
                "total_assertions": total_assertions,
                "aggregate_pass_rate": total_passed / total_assertions if total_assertions else 0,
                "avg_duration_s": sum(r["claude_result"]["duration_s"] for r in config_runs) / len(config_runs),
            }

    # Comparison: with_skill vs old_skill
    if "old_skill" in benchmark["summary"] and "with_skill" in benchmark["summary"]:
        old = benchmark["summary"]["old_skill"]
        new = benchmark["summary"]["with_skill"]
        benchmark["comparison"] = {
            "pass_rate_delta": new["aggregate_pass_rate"] - old["aggregate_pass_rate"],
            "avg_duration_delta_s": new["avg_duration_s"] - old["avg_duration_s"],
            "old_skill_pass_rate": old["aggregate_pass_rate"],
            "with_skill_pass_rate": new["aggregate_pass_rate"],
        }

    # Write benchmark
    output_path = args.output or str(iteration_dir / "benchmark.json")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(benchmark, f, indent=2)
        f.write("\n")

    if args.dry_run:
        print(json.dumps(benchmark, indent=2))
    else:
        print(f"\nBenchmark written to: {output_path}", file=sys.stderr)
        print(json.dumps(benchmark, indent=2))

    if len(completed) == 0 and not args.dry_run:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
