#!/Users/breydentaylor/.local/overshoot-env/bin/python3
"""
Overshoot Vision Router — Adjudication egress for the podcast pipeline.

The visual authority layer: evaluates source footage, generated assets, and
draft assemblies. Counterpart to fal_router.py (generation egress).

Uses the Overshoot Python SDK with FileSource for local video analysis.
Streams results back as structured JSON with the same envelope/job/audit
pattern as fal_router.

Usage:
  # Analyze a local video file
  python3 overshoot_router.py analyze <video_path> --mode source --prompt "..."

  # Analyze with a preset
  python3 overshoot_router.py analyze <video_path> --preset source_assessment

  # Check job status
  python3 overshoot_router.py status <job_id>

  # Get collected results
  python3 overshoot_router.py results <job_id>

  # List available models
  python3 overshoot_router.py models

  # Check spend budget
  python3 overshoot_router.py budget

  # Resolve a show profile
  python3 overshoot_router.py profile <show-slug>
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ZONE_ROOT = Path(__file__).resolve().parents[5]  # canonical/
ENV_FILE = ZONE_ROOT / ".env"
JOBS_DIR = ZONE_ROOT / "audit-logs" / "media-router" / "overshoot-jobs"
RESULTS_DIR = ZONE_ROOT / "audit-logs" / "media-router" / "overshoot-results"
BUDGET_FILE = ZONE_ROOT / "audit-logs" / "media-router" / "budget.json"  # shared with fal

# Production estate — where profiles and outputs live
PRODUCTION_ROOT = ZONE_ROOT.parent / "promptedllc_productions"
PROFILES_DIR = PRODUCTION_ROOT / "profiles"

# ---------------------------------------------------------------------------
# Models — current as of docs.overshoot.ai 2026-03-11, playground 2026-04-12
# ---------------------------------------------------------------------------

MODELS = {
    # Featured (playground-promoted, 2026-04-12)
    "gemma-4-31b": {
        "overshoot_id": "google/gemma-4-31b",
        "tier": "large",
        "note": "Google Gemma 4. Playground-featured, marked Fast.",
    },
    "holo-3": {
        "overshoot_id": "holo-3",
        "tier": "large",
        "note": "New model family. Playground-featured.",
    },
    # Large (27B+) — best quality, slower
    "qwen3.5-35b-a3b": {
        "overshoot_id": "Qwen/Qwen3.5-35B-A3B",
        "tier": "large",
        "note": "MoE, best for throughput-heavy vision and UI agents",
    },
    "qwen3.5-27b": {
        "overshoot_id": "Qwen/Qwen3.5-27B",
        "tier": "large",
        "note": "Dense, best all-rounder. Use for final draft review.",
    },
    "qwen3-vl-32b-fp8": {
        "overshoot_id": "Qwen/Qwen3-VL-32B-Instruct-FP8",
        "tier": "large",
        "note": "Previous gen, FP8 quantized",
    },
    "qwen3-vl-30b-a3b": {
        "overshoot_id": "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "tier": "large",
        "note": "Previous gen MoE",
    },
    "internvl3.5-30b": {
        "overshoot_id": "OpenGVLab/InternVL3_5-30B-A3B",
        "tier": "large",
        "note": "Alternative architecture",
    },
    # Medium (8-9B) — balanced speed/quality
    "qwen3.5-9b": {
        "overshoot_id": "Qwen/Qwen3.5-9B",
        "tier": "medium",
        "note": "Recommended default. Beats last-gen 30B on vision benchmarks.",
    },
    "qwen3-vl-8b": {
        "overshoot_id": "Qwen/Qwen3-VL-8B-Instruct",
        "tier": "medium",
        "note": "Previous gen 8B",
    },
    "molmo2-8b": {
        "overshoot_id": "allenai/Molmo2-8B",
        "tier": "medium",
        "note": "Allen AI, alternative architecture",
    },
    "keye-vl-8b": {
        "overshoot_id": "Kwai-Keye/Keye-VL-1_5-8B",
        "tier": "medium",
        "note": "Kwai model",
    },
    "minicpm-v-4.5": {
        "overshoot_id": "openbmb/MiniCPM-V-4_5",
        "tier": "medium",
        "note": "Compact multimodal",
    },
    # Small (2-4B) — fastest, cheapest
    "qwen3.5-4b": {
        "overshoot_id": "Qwen/Qwen3.5-4B",
        "tier": "small",
        "note": "96% of 27B video score at fraction of size",
    },
    "qwen3.5-2b": {
        "overshoot_id": "Qwen/Qwen3.5-2B",
        "tier": "small",
        "note": "OCR specialist, fastest response time",
    },
    "qwen3-vl-4b": {
        "overshoot_id": "Qwen/Qwen3-VL-4B-Instruct",
        "tier": "small",
        "note": "Previous gen 4B",
    },
}

DEFAULT_MODEL = "qwen3.5-9b"

# Billing: per-second of stream time (not per inference)
# Exact pricing not published in docs — estimate conservatively
COST_PER_SECOND_USD = 0.003  # ~$0.18/min, conservative estimate

# ---------------------------------------------------------------------------
# Processing presets — mirrors playground (Snappy/Balanced/Detailed/Custom)
# Stride = delay_seconds. Effective FPS = (target_fps * clip_length) / stride.
# Max output tokens = floor(128 * stride).
# ---------------------------------------------------------------------------

PROCESSING_PRESETS = {
    "snappy": {
        "target_fps": 6,
        "clip_length_seconds": 0.5,
        "delay_seconds": 0.5,
        "note": "Fast results, 64 max tokens. Good for triage.",
    },
    "balanced": {
        "target_fps": 6,
        "clip_length_seconds": 1.0,
        "delay_seconds": 1.0,
        "note": "Default. 128 max tokens. Good balance of speed and detail.",
    },
    "detailed": {
        "target_fps": 10,
        "clip_length_seconds": 2.0,
        "delay_seconds": 1.5,
        "note": "20 frames/clip, 192 max tokens. Deep analysis.",
    },
}

# ---------------------------------------------------------------------------
# Analysis modes — Visual Adjudication Layer responsibility surfaces
# ---------------------------------------------------------------------------

ANALYSIS_MODES = {
    "source": {
        "description": "Source footage assessment — visual hinges, face windows, edit grammar",
        "mode": "clip",
        "target_fps": 6,
        "clip_length_seconds": 2.0,
        "delay_seconds": 2.0,
        "model": "qwen3.5-9b",
    },
    "generated": {
        "description": "Generated asset assessment — style/intent/likeness fidelity, quality",
        "mode": "frame",
        "interval_seconds": 0.5,
        "model": "qwen3.5-9b",
    },
    "draft": {
        "description": "Draft-level assessment — pacing, transitions, arc coherence",
        "mode": "clip",
        "target_fps": 6,
        "clip_length_seconds": 2.0,
        "delay_seconds": 2.0,
        "model": "qwen3.5-27b",  # best quality for final review
    },
}

# ---------------------------------------------------------------------------
# Presets — structured prompts for each adjudication surface
# ---------------------------------------------------------------------------

PRESETS = {
    "source_assessment": {
        "analysis_mode": "source",
        "prompt": (
            "Analyze this podcast source footage for editorial decision-making. Report:\n"
            "1. VISUAL HINGES — moments where the visual energy shifts (gesture change, "
            "posture shift, expression transition, eye contact change)\n"
            "2. FACE PRIORITY WINDOWS — segments where the speaker's face is well-lit, "
            "in focus, and emotionally expressive (rate 0-1)\n"
            "3. INTERRUPTION-SAFE WINDOWS — segments where cutting away to b-roll would "
            "not disrupt the visual flow\n"
            "4. REACTION MOMENTS — visible reactions from the listener/non-speaking person\n"
            "5. EDIT GRAMMAR — suggest J-cut or L-cut points based on visual energy\n\n"
            "For each finding, provide timestamp offset within this clip."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "visual_hinges": {"type": "array", "items": {"type": "object", "properties": {
                    "offset_sec": {"type": "number"},
                    "description": {"type": "string"},
                    "energy_delta": {"type": "number"},
                }}},
                "face_priority": {"type": "number"},
                "interruption_safe": {"type": "boolean"},
                "reaction_moments": {"type": "array", "items": {"type": "object", "properties": {
                    "offset_sec": {"type": "number"},
                    "description": {"type": "string"},
                }}},
                "edit_suggestion": {"type": "string"},
            },
            "required": ["visual_hinges", "face_priority", "interruption_safe"],
        },
    },
    "generated_assessment": {
        "analysis_mode": "generated",
        "prompt": (
            "Evaluate this AI-generated visual asset for quality and fidelity. Score each:\n"
            "1. STYLE FIDELITY (0-1) — does it match the show's visual language? "
            "(warm gold/amber, deep navy, luminous, organic motion)\n"
            "2. INTENT FIDELITY (0-1) — does it serve the editorial meaning, not just illustrate?\n"
            "3. LIKENESS FIDELITY (0-1) — if a person is depicted, does it preserve their identity?\n"
            "4. QUALITY (0-1) — technical quality, artifact-free, coherent\n"
            "5. ADDITIVE vs DECORATIVE — does this asset add meaning or is it visual wallpaper?\n\n"
            "Be honest. A 0.3 is fine. Say why."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "style_fidelity": {"type": "number"},
                "intent_fidelity": {"type": "number"},
                "likeness_fidelity": {"type": "number"},
                "quality": {"type": "number"},
                "is_additive": {"type": "boolean"},
                "assessment": {"type": "string"},
                "pass": {"type": "boolean"},
            },
            "required": ["style_fidelity", "intent_fidelity", "quality", "is_additive", "pass"],
        },
    },
    "draft_review": {
        "analysis_mode": "draft",
        "prompt": (
            "Review this assembled video draft for editorial coherence. Assess:\n"
            "1. PACING COHERENCE — does the rhythm serve the content? Too fast, too slow, just right?\n"
            "2. TRANSITION COHERENCE — do visual transitions serve the editorial arc or distract?\n"
            "3. B-ROLL CONTINUITY — does generated/overlay imagery flow continuously, or does it "
            "appear chopped, fragmented, or abruptly interrupted mid-motion? A morph or animation "
            "that starts but gets cut before completing is a continuity break. Flag any b-roll that "
            "feels like it was sliced mid-flow by editorial trimming.\n"
            "4. VISUAL OVERREACH — any generated content that draws attention away from the message?\n"
            "5. VISUAL UNDERREACH — any moments begging for visual support that got nothing?\n"
            "6. ARC EXPRESSION — does the final edit still express the intended emotional arc?\n"
            "7. CAPTION SYNC — are captions timed to speech? Any overlap or delay?\n\n"
            "Overall PASS/REVISE verdict with specific revision notes if REVISE."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "pacing": {"type": "string", "enum": ["too_slow", "good", "too_fast", "uneven"]},
                "transition_coherence": {"type": "number"},
                "broll_continuity": {"type": "string", "enum": ["continuous", "minor_breaks", "fragmented"]},
                "broll_continuity_notes": {"type": "array", "items": {"type": "string"}},
                "overreach_moments": {"type": "array", "items": {"type": "string"}},
                "underreach_moments": {"type": "array", "items": {"type": "string"}},
                "arc_expression": {"type": "number"},
                "caption_sync": {"type": "string", "enum": ["good", "minor_issues", "major_issues"]},
                "verdict": {"type": "string", "enum": ["pass", "revise"]},
                "revision_notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pacing", "broll_continuity", "arc_expression", "verdict"],
        },
    },
}


# ---------------------------------------------------------------------------
# Profile resolution
# ---------------------------------------------------------------------------

def resolve_profile(show_slug):
    """
    Resolve a show profile by slug. Search order:
    1. T7 Shield production assets (external drive)
    2. promptedllc_productions/profiles/{slug}.profile.json
    3. canonical/profiles/{slug}.profile.json (legacy, pre-move)
    """
    t7_profiles = Path("/Volumes/T7 Shield/eeShow/profiles")
    candidates = [
        t7_profiles / f"{show_slug}.profile.json",
        PROFILES_DIR / f"{show_slug}.profile.json",
        ZONE_ROOT / "profiles" / f"{show_slug}.profile.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())
    return None


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_overshoot_key():
    """Load OVERSHOOT_API_KEY from canonical/.env"""
    key = os.environ.get("OVERSHOOT_API_KEY")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("OVERSHOOT_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["OVERSHOOT_API_KEY"] = key
                return key
    print("ERROR: OVERSHOOT_API_KEY not found. Set it in canonical/.env or environment.",
          file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Budget enforcement (shared budget surface with fal_router)
# ---------------------------------------------------------------------------

def load_budget():
    if BUDGET_FILE.exists():
        budget = json.loads(BUDGET_FILE.read_text())
        if budget.get("window_start"):
            start = datetime.fromisoformat(budget["window_start"])
            window_h = budget.get("window_hours", 24)
            if datetime.now(timezone.utc) > start + timedelta(hours=window_h):
                budget["spent_usd"] = 0.0
                budget["jobs_in_window"] = 0
                budget["window_start"] = datetime.now(timezone.utc).isoformat()
                save_budget(budget)
        return budget
    budget = {"cap_usd": 25.0, "window_hours": 24,
              "window_start": datetime.now(timezone.utc).isoformat(),
              "spent_usd": 0.0, "jobs_in_window": 0, "max_single_job_usd": 5.0}
    save_budget(budget)
    return budget


def save_budget(budget):
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(budget, indent=2) + "\n")


def estimate_cost(duration_seconds):
    """Estimate stream cost from video duration."""
    return round(COST_PER_SECOND_USD * duration_seconds, 4)


def check_budget(estimated_cost):
    budget = load_budget()
    remaining = budget["cap_usd"] - budget["spent_usd"]
    if estimated_cost > budget.get("max_single_job_usd", 5.0):
        return False, f"Single job ${estimated_cost:.2f} exceeds max ${budget['max_single_job_usd']:.2f}", budget
    if estimated_cost > remaining:
        return False, f"Would exceed budget: ${estimated_cost:.2f} requested, ${remaining:.2f} remaining", budget
    return True, "ok", budget


def record_spend(estimated_cost):
    budget = load_budget()
    budget["spent_usd"] = round(budget["spent_usd"] + estimated_cost, 4)
    budget["jobs_in_window"] += 1
    save_budget(budget)
    return budget


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def ensure_dirs():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def create_job_record(video_path, analysis_mode, model_key, prompt, estimated_cost):
    job_id = f"ovs_{uuid.uuid4().hex[:12]}"
    record = {
        "job_id": job_id,
        "video_path": str(video_path),
        "analysis_mode": analysis_mode,
        "model": model_key,
        "overshoot_model_id": MODELS[model_key]["overshoot_id"],
        "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
        "status": "submitted",
        "estimated_cost_usd": estimated_cost,
        "actual_cost_usd": None,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "result_count": 0,
        "stream_id": None,
        "error": None,
    }
    (JOBS_DIR / f"{job_id}.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def update_job(job_id, updates):
    path = JOBS_DIR / f"{job_id}.json"
    record = json.loads(path.read_text())
    record.update(updates)
    path.write_text(json.dumps(record, indent=2) + "\n")
    return record


def load_job(job_id):
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_results(job_id, results):
    path = RESULTS_DIR / f"{job_id}.json"
    path.write_text(json.dumps({"job_id": job_id, "results": results}, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Overshoot dispatch — async, uses Python SDK with FileSource
# ---------------------------------------------------------------------------

async def dispatch_analyze(video_path, analysis_mode, model_key, prompt,
                           output_schema=None, max_duration_sec=120):
    """
    Analyze a local video file using the Overshoot Python SDK.
    Streams results via FileSource, collects them, returns when video ends or timeout.
    """
    try:
        import overshoot
    except ImportError:
        print("ERROR: overshoot SDK not installed. Run: pip install git+https://github.com/Overshoot-ai/overshoot-python.git",
              file=sys.stderr)
        sys.exit(1)

    api_key = load_overshoot_key()
    video = Path(video_path)
    if not video.exists():
        return {"error": f"Video not found: {video_path}"}

    # Get video duration for cost estimation
    duration_sec = _get_video_duration(video)
    if duration_sec is None:
        duration_sec = max_duration_sec  # fallback estimate

    estimated = estimate_cost(min(duration_sec, max_duration_sec))
    allowed, reason, budget = check_budget(estimated)
    if not allowed:
        return {"error": reason, "budget": budget}

    mode_config = ANALYSIS_MODES.get(analysis_mode, ANALYSIS_MODES["source"])
    model_id = MODELS[model_key]["overshoot_id"]

    record = create_job_record(video_path, analysis_mode, model_key, prompt, estimated)
    results = []
    errors = []

    def on_result(r):
        entry = {
            "ok": r.ok,
            "result": r.result if hasattr(r, 'result') else str(r),
            "inference_latency_ms": getattr(r, 'inference_latency_ms', None),
            "total_latency_ms": getattr(r, 'total_latency_ms', None),
            "finish_reason": getattr(r, 'finish_reason', None),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(r, 'error') and r.error:
            entry["error"] = r.error
            errors.append(entry)
        results.append(entry)
        print(f"  [{record['job_id']}] Result {len(results)}: "
              f"{'OK' if r.ok else 'ERR'} ({getattr(r, 'inference_latency_ms', '?')}ms)",
              file=sys.stderr)

    def on_error(err):
        errors.append({"error": str(err), "at": datetime.now(timezone.utc).isoformat()})
        print(f"  [{record['job_id']}] Error: {err}", file=sys.stderr)

    # Build SDK params based on analysis mode
    create_kwargs = {
        "source": overshoot.FileSource(path=str(video), loop=False),
        "prompt": prompt,
        "model": model_id,
        "on_result": on_result,
        "on_error": on_error,
        "mode": mode_config["mode"],
    }

    if output_schema:
        create_kwargs["output_schema"] = output_schema

    # Add mode-specific processing params
    if mode_config["mode"] == "clip":
        create_kwargs["target_fps"] = mode_config.get("target_fps", 6)
        create_kwargs["clip_length_seconds"] = mode_config.get("clip_length_seconds", 0.5)
        create_kwargs["delay_seconds"] = mode_config.get("delay_seconds", 0.5)
    else:
        create_kwargs["interval_seconds"] = mode_config.get("interval_seconds", 0.5)

    # Create client and stream
    client = overshoot.Overshoot(api_key=api_key)
    try:
        stream = await client.streams.create(**create_kwargs)
        update_job(record["job_id"], {
            "status": "streaming",
            "stream_id": stream.stream_id,
        })

        # Wait for video to finish (FileSource with loop=False ends naturally)
        # or timeout
        stream_duration = min(duration_sec + 10, max_duration_sec)
        await asyncio.sleep(stream_duration)

        await stream.close()
        await client.close()

        record_spend(estimated)
        save_results(record["job_id"], results)

        update_job(record["job_id"], {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_count": len(results),
            "error_count": len(errors),
        })

        return {
            "job_id": record["job_id"],
            "status": "completed",
            "result_count": len(results),
            "error_count": len(errors),
            "results": results,
        }

    except Exception as e:
        update_job(record["job_id"], {"status": "error", "error": str(e)})
        try:
            await client.close()
        except Exception:
            pass
        return {"error": str(e), "job_id": record["job_id"]}


def _get_video_duration(video_path):
    """Get video duration via ffprobe."""
    import subprocess
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video_path)],
            capture_output=True, text=True
        )
        return float(json.loads(probe.stdout)["format"]["duration"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Completion hook
# ---------------------------------------------------------------------------

def fire_completion_hook(record, results):
    hook_dir = ZONE_ROOT / "audit-logs" / "media-router" / "overshoot-completions"
    hook_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "overshoot_analysis_complete",
        "job_id": record["job_id"],
        "analysis_mode": record["analysis_mode"],
        "model": record["model"],
        "result_count": len(results),
        "video_path": record["video_path"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }
    (hook_dir / f"{record['job_id']}.json").write_text(json.dumps(event, indent=2) + "\n")
    print(json.dumps(event))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_analyze(args):
    analysis_mode = args.mode or "source"
    model_key = args.model or ANALYSIS_MODES.get(analysis_mode, {}).get("model", DEFAULT_MODEL)

    if model_key not in MODELS:
        print(f"ERROR: Unknown model '{model_key}'. Available: {', '.join(MODELS.keys())}",
              file=sys.stderr)
        sys.exit(1)

    # Resolve prompt from preset or direct
    output_schema = None
    if args.preset:
        if args.preset not in PRESETS:
            print(f"ERROR: Unknown preset '{args.preset}'. Available: {', '.join(PRESETS.keys())}",
                  file=sys.stderr)
            sys.exit(1)
        preset = PRESETS[args.preset]
        prompt = args.prompt or preset["prompt"]
        output_schema = preset.get("output_schema")
        if not args.mode:
            analysis_mode = preset.get("analysis_mode", analysis_mode)
            model_key = ANALYSIS_MODES.get(analysis_mode, {}).get("model", model_key)
    else:
        prompt = args.prompt
        if not prompt:
            print("ERROR: Provide --prompt or --preset", file=sys.stderr)
            sys.exit(1)

    if args.model:
        model_key = args.model

    print(f"Analyzing: {args.video_path}", file=sys.stderr)
    print(f"  Mode: {analysis_mode} | Model: {model_key} ({MODELS[model_key]['overshoot_id']})",
          file=sys.stderr)

    result = asyncio.run(dispatch_analyze(
        args.video_path, analysis_mode, model_key, prompt,
        output_schema=output_schema,
        max_duration_sec=args.max_duration,
    ))
    print(json.dumps(result, indent=2, default=str))


def cmd_status(args):
    record = load_job(args.job_id)
    if not record:
        print(json.dumps({"error": f"Job {args.job_id} not found"}))
        return
    print(json.dumps(record, indent=2, default=str))


def cmd_results(args):
    path = RESULTS_DIR / f"{args.job_id}.json"
    if not path.exists():
        print(json.dumps({"error": f"No results for {args.job_id}"}))
        return
    data = json.loads(path.read_text())
    print(json.dumps(data, indent=2, default=str))


def cmd_models(args):
    print("Available Overshoot models:\n")
    for tier in ["large", "medium", "small"]:
        models = {k: v for k, v in MODELS.items() if v["tier"] == tier}
        if models:
            print(f"  {tier.upper()}:")
            for key, info in models.items():
                default = " (default)" if key == DEFAULT_MODEL else ""
                print(f"    {key:20s}  {info['overshoot_id']:45s}  {info['note']}{default}")
            print()


def cmd_presets(args):
    print("Available analysis presets:\n")
    for name, preset in PRESETS.items():
        mode = preset.get("analysis_mode", "source")
        model = ANALYSIS_MODES.get(mode, {}).get("model", DEFAULT_MODEL)
        print(f"  {name:25s}  mode={mode:10s}  model={model}")
        print(f"    {preset['prompt'][:100]}...")
        print()


def cmd_profile(args):
    profile = resolve_profile(args.show_slug)
    if not profile:
        print(json.dumps({"error": f"No profile found for '{args.show_slug}'",
                          "searched": [str(PROFILES_DIR), str(ZONE_ROOT / "profiles")]}))
        return
    print(json.dumps(profile, indent=2))


def cmd_budget(args):
    budget = load_budget()
    remaining = budget["cap_usd"] - budget["spent_usd"]
    print(f"Shared media budget: ${budget['spent_usd']:.2f} / ${budget['cap_usd']:.2f} "
          f"(${remaining:.2f} remaining)")
    print(f"Window: {budget['window_hours']}h from {budget.get('window_start', 'unset')}")
    print(f"Jobs in window: {budget['jobs_in_window']}")


def main():
    parser = argparse.ArgumentParser(description="Overshoot Vision Router — Adjudication Egress")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="Analyze a local video file")
    p_analyze.add_argument("video_path", help="Path to video file")
    p_analyze.add_argument("--mode", choices=list(ANALYSIS_MODES.keys()),
                           help="Analysis mode (source/generated/draft)")
    p_analyze.add_argument("--model", choices=list(MODELS.keys()),
                           help="Model to use")
    p_analyze.add_argument("--prompt", help="Analysis prompt (or use --preset)")
    p_analyze.add_argument("--preset", choices=list(PRESETS.keys()),
                           help="Use a preset prompt")
    p_analyze.add_argument("--max-duration", type=int, default=120,
                           help="Max stream duration in seconds (default 120)")
    p_analyze.set_defaults(func=cmd_analyze)

    p_status = sub.add_parser("status", help="Check job status")
    p_status.add_argument("job_id", help="Job ID")
    p_status.set_defaults(func=cmd_status)

    p_results = sub.add_parser("results", help="Get job results")
    p_results.add_argument("job_id", help="Job ID")
    p_results.set_defaults(func=cmd_results)

    p_models = sub.add_parser("models", help="List available models")
    p_models.set_defaults(func=cmd_models)

    p_presets = sub.add_parser("presets", help="List analysis presets")
    p_presets.set_defaults(func=cmd_presets)

    p_profile = sub.add_parser("profile", help="Resolve a show profile by slug")
    p_profile.add_argument("show_slug", help="Show slug (e.g. everythings-energy)")
    p_profile.set_defaults(func=cmd_profile)

    p_budget = sub.add_parser("budget", help="View spend budget (shared with fal)")
    p_budget.set_defaults(func=cmd_budget)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
