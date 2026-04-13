#!/usr/bin/env python3
"""
fal.ai Media Router — Egress adapter for the podcast pipeline.

The agentic side writes structured generation requests as JSON envelopes.
This router dispatches them to fal.ai, enforces spend caps and time windows,
tracks job state, and fires completion hooks back to the main thread.

Usage:
  # Submit a job (async, returns immediately with job ID)
  python3 fal_router.py submit <envelope.json>

  # Check job status
  python3 fal_router.py status <job_id>

  # Get job result (blocks until complete or timeout)
  python3 fal_router.py result <job_id> [--timeout 300]

  # Subscribe (submit + block until result)
  python3 fal_router.py subscribe <envelope.json>

  # Check spend budget
  python3 fal_router.py budget

  # Reset spend window (manual override)
  python3 fal_router.py budget reset
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ZONE_ROOT = Path(__file__).resolve().parents[5]  # canonical/
ENV_FILE = ZONE_ROOT / ".env"
JOBS_DIR = ZONE_ROOT / "audit-logs" / "media-router" / "jobs"
BUDGET_FILE = ZONE_ROOT / "audit-logs" / "media-router" / "budget.json"
ASSETS_DIR = ZONE_ROOT / "audit-logs" / "media-router" / "assets"

# Model registry — exact fal.ai model IDs and their cost models
MODELS = {
    "nano-banana-2": {
        "fal_id": "fal-ai/nano-banana-2",
        "type": "image",
        "cost_per_unit": 0.08,  # per image at 1K
        "unit": "image",
        "resolution_multipliers": {"512x512": 0.75, "1K": 1.0, "2K": 1.5, "4K": 2.0},
    },
    "kling-v3-pro-i2v": {
        "fal_id": "fal-ai/kling-video/v3/pro/image-to-video",
        "type": "video",
        "cost_per_unit": 0.112,  # per second, audio off
        "cost_per_unit_audio": 0.168,  # per second, audio on
        "unit": "second",
    },
    "seedance-2.0-i2v": {
        "fal_id": "bytedance/seedance-2.0/image-to-video",
        "type": "video",
        "cost_per_unit": 0.3024,  # per second at 720p
        "unit": "second",
    },
    "seedance-2.0-r2v": {
        "fal_id": "bytedance/seedance-2.0/reference-to-video",
        "type": "video",
        "cost_per_unit": 0.3024,  # per second at 720p (same pricing tier)
        "unit": "second",
        "max_images": 9,
        "max_videos": 3,
        "max_audio": 3,
    },
}

# Reverse lookup: fal_id -> our model key
FAL_ID_TO_KEY = {m["fal_id"]: k for k, m in MODELS.items()}

# Default spend caps
DEFAULT_BUDGET = {
    "cap_usd": 25.00,
    "window_hours": 24,
    "window_start": None,
    "spent_usd": 0.0,
    "jobs_in_window": 0,
    "max_single_job_usd": 5.00,  # no single job can exceed this
}


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_fal_key():
    """Load FAL_KEY from canonical/.env"""
    key = os.environ.get("FAL_KEY")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("FAL_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["FAL_KEY"] = key
                return key
    print("ERROR: FAL_KEY not found. Set it in canonical/.env or environment.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------

def ensure_dirs():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def load_budget():
    if BUDGET_FILE.exists():
        budget = json.loads(BUDGET_FILE.read_text())
        # Check if window has expired — auto-reset
        if budget.get("window_start"):
            start = datetime.fromisoformat(budget["window_start"])
            window_h = budget.get("window_hours", DEFAULT_BUDGET["window_hours"])
            if datetime.now(timezone.utc) > start + timedelta(hours=window_h):
                budget["spent_usd"] = 0.0
                budget["jobs_in_window"] = 0
                budget["window_start"] = datetime.now(timezone.utc).isoformat()
                save_budget(budget)
        return budget
    budget = {**DEFAULT_BUDGET, "window_start": datetime.now(timezone.utc).isoformat()}
    save_budget(budget)
    return budget


def save_budget(budget):
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(budget, indent=2) + "\n")


def estimate_cost(envelope):
    """Estimate job cost from envelope params."""
    model_key = envelope.get("model")
    if model_key not in MODELS:
        return 0.0
    model = MODELS[model_key]
    if model["type"] == "image":
        n = envelope.get("params", {}).get("num_images", 1)
        res = envelope.get("params", {}).get("resolution", "1K")
        mult = model["resolution_multipliers"].get(res, 1.0)
        return model["cost_per_unit"] * n * mult
    elif model["type"] == "video":
        dur_raw = envelope.get("params", {}).get("duration", "5")
        duration = int(dur_raw) if dur_raw != "auto" else 8  # conservative estimate for auto
        if model_key == "kling-v3-pro-i2v":
            audio = envelope.get("params", {}).get("generate_audio", True)
            rate = model["cost_per_unit_audio"] if audio else model["cost_per_unit"]
        else:
            rate = model["cost_per_unit"]
        return rate * duration
    return 0.0


def check_budget(estimated_cost):
    """Returns (allowed: bool, reason: str, budget: dict)"""
    budget = load_budget()
    remaining = budget["cap_usd"] - budget["spent_usd"]

    if estimated_cost > budget.get("max_single_job_usd", 5.0):
        return False, f"Single job ${estimated_cost:.2f} exceeds max ${budget['max_single_job_usd']:.2f}", budget
    if estimated_cost > remaining:
        return False, f"Would exceed budget: ${estimated_cost:.2f} requested, ${remaining:.2f} remaining of ${budget['cap_usd']:.2f} window", budget
    return True, "ok", budget


def record_spend(estimated_cost):
    budget = load_budget()
    budget["spent_usd"] = round(budget["spent_usd"] + estimated_cost, 4)
    budget["jobs_in_window"] += 1
    save_budget(budget)
    return budget


# ---------------------------------------------------------------------------
# Envelope → fal params translation
# ---------------------------------------------------------------------------

def translate_envelope(envelope):
    """
    Translate a pipeline envelope (natural-language-adjacent params)
    into the exact fal.ai API params for the target model.
    """
    model_key = envelope["model"]
    model = MODELS[model_key]
    fal_id = model["fal_id"]
    params = envelope.get("params", {})

    if model_key == "nano-banana-2":
        fal_params = {
            "prompt": params["prompt"],
        }
        for opt in ["aspect_ratio", "num_images", "output_format", "resolution",
                     "negative_prompt"]:
            if opt in params:
                fal_params[opt] = params[opt]
        return fal_id, fal_params

    elif model_key == "kling-v3-pro-i2v":
        fal_params = {
            "start_image_url": params["image_url"],
            "prompt": params["prompt"],
            "duration": str(params.get("duration", "5")),
        }
        for opt in ["aspect_ratio", "negative_prompt", "generate_audio",
                     "end_image_url", "elements", "cfg_scale"]:
            if opt in params:
                fal_params[opt] = params[opt]
        return fal_id, fal_params

    elif model_key == "seedance-2.0-i2v":
        fal_params = {
            "image_url": params["image_url"],
            "prompt": params["prompt"],
            "duration": str(params.get("duration", "5")),
        }
        for opt in ["aspect_ratio", "resolution", "audio", "end_frame"]:
            if opt in params:
                fal_params[opt] = params[opt]
        if "end_image_url" in params and "end_frame" not in params:
            fal_params["end_frame"] = params["end_image_url"]
        return fal_id, fal_params

    elif model_key == "seedance-2.0-r2v":
        fal_params = {
            "prompt": params["prompt"],
        }
        # Reference arrays — up to 9 images, 3 videos, 3 audio
        if "image_urls" in params:
            fal_params["image_urls"] = params["image_urls"][:9]
        if "video_urls" in params:
            fal_params["video_urls"] = params["video_urls"][:3]
        if "audio_urls" in params:
            fal_params["audio_urls"] = params["audio_urls"][:3]
        for opt in ["aspect_ratio", "resolution", "duration", "generate_audio", "seed"]:
            if opt in params:
                fal_params[opt] = params[opt]
        return fal_id, fal_params

    else:
        raise ValueError(f"Unknown model: {model_key}")


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def create_job_record(envelope, estimated_cost):
    job_id = f"fal_{uuid.uuid4().hex[:12]}"
    record = {
        "job_id": job_id,
        "model": envelope["model"],
        "fal_model_id": MODELS[envelope["model"]]["fal_id"],
        "asset_type": MODELS[envelope["model"]]["type"],
        "status": "submitted",
        "estimated_cost_usd": estimated_cost,
        "actual_cost_usd": None,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "fal_request_id": None,
        "result_url": None,
        "local_asset_path": None,
        "envelope": envelope,
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


# ---------------------------------------------------------------------------
# fal.ai dispatch
# ---------------------------------------------------------------------------

def dispatch_submit(envelope):
    """Submit async (non-blocking). Returns job record."""
    import fal_client

    load_fal_key()
    estimated = estimate_cost(envelope)
    allowed, reason, budget = check_budget(estimated)
    if not allowed:
        return {"error": reason, "budget": budget}

    fal_id, fal_params = translate_envelope(envelope)
    record = create_job_record(envelope, estimated)

    try:
        handler = fal_client.submit(fal_id, arguments=fal_params)
        request_id = handler.request_id
        update_job(record["job_id"], {
            "fal_request_id": request_id,
            "status": "queued",
        })
        record_spend(estimated)
        record["fal_request_id"] = request_id
        record["status"] = "queued"
        return record
    except Exception as e:
        update_job(record["job_id"], {"status": "error", "error": str(e)})
        record["status"] = "error"
        record["error"] = str(e)
        return record


def dispatch_subscribe(envelope):
    """Submit and block until result. Returns job record with result."""
    import fal_client

    load_fal_key()
    estimated = estimate_cost(envelope)
    allowed, reason, budget = check_budget(estimated)
    if not allowed:
        return {"error": reason, "budget": budget}

    fal_id, fal_params = translate_envelope(envelope)
    record = create_job_record(envelope, estimated)
    record_spend(estimated)

    try:
        def on_queue_update(update):
            if hasattr(update, 'logs') and update.logs:
                for log in update.logs:
                    print(f"  [{record['job_id']}] {log.get('message', log)}", file=sys.stderr)

        result = fal_client.subscribe(fal_id, arguments=fal_params,
                                       with_logs=True, on_queue_update=on_queue_update)

        # Extract result URL based on asset type
        if MODELS[envelope["model"]]["type"] == "image":
            result_url = result.get("images", [{}])[0].get("url")
        else:
            result_url = result.get("video", {}).get("url")

        update_job(record["job_id"], {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_url": result_url,
            "result_raw": result,
        })
        record["status"] = "completed"
        record["result_url"] = result_url

        # Fire completion hook
        fire_completion_hook(record)
        return record

    except Exception as e:
        update_job(record["job_id"], {"status": "error", "error": str(e)})
        record["status"] = "error"
        record["error"] = str(e)
        return record


def check_status(job_id):
    """Check status of an async job."""
    import fal_client

    load_fal_key()
    record = load_job(job_id)
    if not record:
        return {"error": f"Job {job_id} not found"}

    if record["status"] in ("completed", "error"):
        return record

    if not record.get("fal_request_id"):
        return record

    try:
        status = fal_client.status(record["fal_model_id"],
                                    record["fal_request_id"],
                                    with_logs=False)
        if hasattr(status, 'status'):
            update_job(job_id, {"status": status.status})
            record["status"] = status.status
        return record
    except Exception as e:
        return {**record, "status_check_error": str(e)}


def get_result(job_id, timeout=300):
    """Block until job completes or timeout."""
    import fal_client

    load_fal_key()
    record = load_job(job_id)
    if not record:
        return {"error": f"Job {job_id} not found"}

    if record["status"] == "completed":
        return record

    if not record.get("fal_request_id"):
        return {"error": "Job has no fal request ID"}

    try:
        result = fal_client.result(record["fal_model_id"],
                                    record["fal_request_id"])

        model_key = record["model"]
        if MODELS[model_key]["type"] == "image":
            result_url = result.get("images", [{}])[0].get("url")
        else:
            result_url = result.get("video", {}).get("url")

        updated = update_job(job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_url": result_url,
            "result_raw": result,
        })
        fire_completion_hook(updated)
        return updated

    except Exception as e:
        return {**record, "result_error": str(e)}


# ---------------------------------------------------------------------------
# Completion hook — fires back to main thread
# ---------------------------------------------------------------------------

def fire_completion_hook(record):
    """
    Write a completion event that the session hook system can detect.
    The hook file contains the job ID, asset type, result URL, and cost.
    """
    hook_dir = ZONE_ROOT / "audit-logs" / "media-router" / "completions"
    hook_dir.mkdir(parents=True, exist_ok=True)

    event = {
        "event": "media_generation_complete",
        "job_id": record["job_id"],
        "model": record["model"],
        "asset_type": record.get("asset_type", MODELS.get(record["model"], {}).get("type")),
        "result_url": record.get("result_url"),
        "estimated_cost_usd": record.get("estimated_cost_usd"),
        "completed_at": record.get("completed_at") or datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }

    event_path = hook_dir / f"{record['job_id']}.json"
    event_path.write_text(json.dumps(event, indent=2) + "\n")

    # Also print to stdout for inline capture
    print(json.dumps(event))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_submit(args):
    envelope = json.loads(Path(args.envelope).read_text())
    result = dispatch_submit(envelope)
    print(json.dumps(result, indent=2, default=str))


def cmd_subscribe(args):
    envelope = json.loads(Path(args.envelope).read_text())
    result = dispatch_subscribe(envelope)
    print(json.dumps(result, indent=2, default=str))


def cmd_status(args):
    result = check_status(args.job_id)
    print(json.dumps(result, indent=2, default=str))


def cmd_result(args):
    result = get_result(args.job_id, timeout=args.timeout)
    print(json.dumps(result, indent=2, default=str))


def cmd_extract_frames(args):
    """Extract evenly-spaced frames from a video for reference array input."""
    import subprocess
    src = Path(args.source)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(1)

    n = args.count
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(src)],
        capture_output=True, text=True
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    # Calculate timestamps for even spacing
    if args.start is not None and args.end is not None:
        start_t, end_t = args.start, args.end
    else:
        start_t, end_t = 0, duration

    interval = (end_t - start_t) / n
    timestamps = [start_t + i * interval for i in range(n)]

    paths = []
    for i, ts in enumerate(timestamps):
        out_path = out_dir / f"ref_{i+1:02d}_{ts:.2f}s.png"
        subprocess.run([
            "ffmpeg", "-v", "quiet", "-ss", str(ts), "-i", str(src),
            "-frames:v", "1", "-q:v", "2", str(out_path), "-y"
        ])
        paths.append(str(out_path))
        print(f"  Frame {i+1}/{n}: {ts:.2f}s -> {out_path.name}")

    result = {
        "source": str(src),
        "frame_count": n,
        "interval_seconds": interval,
        "timestamps": timestamps,
        "paths": paths,
    }
    print(json.dumps(result, indent=2))


def cmd_budget(args):
    if args.action == "reset":
        budget = {**DEFAULT_BUDGET, "window_start": datetime.now(timezone.utc).isoformat()}
        save_budget(budget)
        print("Budget reset.")
        print(json.dumps(budget, indent=2))
    elif args.action == "set":
        budget = load_budget()
        if args.cap:
            budget["cap_usd"] = float(args.cap)
        if args.window:
            budget["window_hours"] = int(args.window)
        if args.max_job:
            budget["max_single_job_usd"] = float(args.max_job)
        save_budget(budget)
        print("Budget updated.")
        print(json.dumps(budget, indent=2))
    else:
        budget = load_budget()
        remaining = budget["cap_usd"] - budget["spent_usd"]
        print(f"Budget: ${budget['spent_usd']:.2f} / ${budget['cap_usd']:.2f} "
              f"(${remaining:.2f} remaining)")
        print(f"Window: {budget['window_hours']}h from {budget.get('window_start', 'unset')}")
        print(f"Jobs in window: {budget['jobs_in_window']}")
        print(f"Max single job: ${budget.get('max_single_job_usd', 5.0):.2f}")


def main():
    parser = argparse.ArgumentParser(description="fal.ai Media Router")
    sub = parser.add_subparsers(dest="command")

    p_submit = sub.add_parser("submit", help="Submit async job")
    p_submit.add_argument("envelope", help="Path to envelope JSON")
    p_submit.set_defaults(func=cmd_submit)

    p_subscribe = sub.add_parser("subscribe", help="Submit and wait for result")
    p_subscribe.add_argument("envelope", help="Path to envelope JSON")
    p_subscribe.set_defaults(func=cmd_subscribe)

    p_status = sub.add_parser("status", help="Check job status")
    p_status.add_argument("job_id", help="Job ID")
    p_status.set_defaults(func=cmd_status)

    p_result = sub.add_parser("result", help="Get job result (blocking)")
    p_result.add_argument("job_id", help="Job ID")
    p_result.add_argument("--timeout", type=int, default=300)
    p_result.set_defaults(func=cmd_result)

    p_extract = sub.add_parser("extract-frames", help="Extract reference frame array from video")
    p_extract.add_argument("source", help="Source video path")
    p_extract.add_argument("--count", "-n", type=int, default=8, help="Number of frames (default 8, max 9 for Seedance r2v)")
    p_extract.add_argument("--output-dir", "-o", default="./output/ref-frames", help="Output directory")
    p_extract.add_argument("--start", type=float, default=None, help="Start time in seconds")
    p_extract.add_argument("--end", type=float, default=None, help="End time in seconds")
    p_extract.set_defaults(func=cmd_extract_frames)

    p_budget = sub.add_parser("budget", help="View or manage spend budget")
    p_budget.add_argument("action", nargs="?", default="show",
                          choices=["show", "reset", "set"])
    p_budget.add_argument("--cap", help="Set cap in USD")
    p_budget.add_argument("--window", help="Set window in hours")
    p_budget.add_argument("--max-job", help="Set max single job in USD")
    p_budget.set_defaults(func=cmd_budget)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
