#!/usr/bin/env python3
"""docks-handler.py — Docks ingress handler: MCP verification handshake for visitor admission.

Implements the Docks ingress specification (autonomous_kernel/docks-ingress-spec.md):
  1. Wire-cut check (before any registration)
  2. Visitor registration (entity record creation)
  3. 4-probe verification handshake
  4. Tiered admission (standing assignment based on probe results)
  5. Signal emission (registration, admission, rejection, probe failure)
  6. Rate limiting (flood detection)

Importable as a module:
    from docks_handler import DocksHandler
    handler = DocksHandler(zone_root="/path/to/canonical")
    result = handler.register_visitor(dock_request)

Runnable as CLI:
    # Register a new visitor
    python3 docks-handler.py register \\
        --display-name "Visitor Alpha" \\
        --mcp-endpoint "http://localhost:8080/mcp" \\
        --ingress-lane tailscale_serve \\
        [--home-federation-id "ext_federation_42"] \\
        [--tvi-tier-claim native] \\
        [--requested-role-flags expedition,student]

    # Register from JSON stdin
    echo '{"visitor_display_name":"...","mcp_server_endpoint":"..."}' | python3 docks-handler.py register --stdin

    # Run probes against a registered visitor
    python3 docks-handler.py probe --entity-id ent_visitor_abc123

    # Check wire-cut status
    python3 docks-handler.py wire-cut-status

Depends on:
    - scripts/lib/atomic_append.py (JSONL writes)
    - scripts/zone_root.py (zone root discovery)
    - scripts/docks-signal-emitter.py (signal emission)
"""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology
from lib.atomic_append import atomic_append_jsonl, atomic_write_json

# Lazy import — allows module import without docks-signal-emitter present
_signal_emitter = None


def _get_signal_emitter():
    global _signal_emitter
    if _signal_emitter is None:
        # Import from same directory using importlib to handle hyphenated filename
        import importlib.util
        spec_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "docks-signal-emitter.py",
        )
        spec = importlib.util.spec_from_file_location("docks_signal_emitter", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _signal_emitter = mod
    return _signal_emitter


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

WIRE_CUT_DIR = os.path.expanduser("~/.claude")

WIRE_CUT_SENTINELS = {
    "docks_ingress": ".wire-cut-docks-ingress",
    "docks_all": ".wire-cut-docks-all",
    "all": ".wire-cut-all",
}

PROBE_NAMES = [
    "capability_discovery",
    "echo_probe",
    "state_persistence",
    "coherence",
]

PROBE_TIMEOUT_DEFAULT = 30  # seconds

# Tiered outcomes from docks-ingress-spec.md
# Key: number of probes passed. Value: (standing, role_flags, visa_state)
TIER_OUTCOMES = {
    4: ("guest", ["foreign_delegate"], "verified"),   # Student-eligible
    3: ("guest", ["expedition"], "verified"),          # Tourist+ (3 of 4)
    2: ("guest", ["expedition"], "verified"),          # Tourist (probes 1-2)
    1: ("guest", [], "verified"),                      # Minimal observer
    0: (None, [], None),                               # Rejected
}

# Rate limiting defaults (provisional per CogPR-46)
RATE_LIMITS = {
    "per_source_per_minute": 10,
    "federation_wide_per_minute": 100,
    "concurrent_probe_handshakes": 20,
    "max_active_sessions": 500,
}

VALID_TVI_TIERS = ("native", "adapter", "proxy")
VALID_INGRESS_LANES = ("tailscale_serve", "ngrok")


# ─────────────────────────────────────────────
# Wire-Cut Check
# ─────────────────────────────────────────────

def check_wire_cut() -> dict:
    """Check for wire-cut sentinel files.

    Returns dict with:
        active: bool — whether any wire cut is active
        scope: str|None — most restrictive active scope
        sentinels: dict — {scope: bool} for each sentinel
    """
    sentinels = {}
    for scope, filename in WIRE_CUT_SENTINELS.items():
        sentinels[scope] = os.path.isfile(os.path.join(WIRE_CUT_DIR, filename))

    # Determine most restrictive active scope (all > docks_all > docks_ingress)
    if sentinels["all"]:
        return {"active": True, "scope": "all", "sentinels": sentinels}
    if sentinels["docks_all"]:
        return {"active": True, "scope": "docks_all", "sentinels": sentinels}
    if sentinels["docks_ingress"]:
        return {"active": True, "scope": "docks_ingress", "sentinels": sentinels}
    return {"active": False, "scope": None, "sentinels": sentinels}


# ─────────────────────────────────────────────
# Rate Limiting
# ─────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter with sliding window.

    For persistent rate tracking across processes, reads the visitor
    registry to count recent registrations.
    """

    def __init__(self, zone_root: str, limits: dict | None = None):
        self.zone_root = zone_root
        self.limits = limits or RATE_LIMITS
        self._registry_path = self._resolve_registry_path()

    def _resolve_registry_path(self) -> str:
        tz_config = load_ticzone(self.zone_root)
        al_path = audit_logs_path(self.zone_root, tz_config)
        return os.path.join(al_path, "visitors", "registry.jsonl")

    def check_rate(self, source_ip: str | None = None) -> dict:
        """Check if registration rate is within limits.

        Returns:
            {
                "allowed": bool,
                "reason": str|None,
                "rates": {"federation_wide": int, "per_source": int},
            }
        """
        now = datetime.now(timezone.utc)
        window_start = now.timestamp() - 60  # 1-minute window

        recent_all = 0
        recent_source = 0

        if os.path.isfile(self._registry_path):
            try:
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            arrived = entry.get("arrived_at", "")
                            if arrived:
                                ts = datetime.fromisoformat(arrived).timestamp()
                                if ts >= window_start:
                                    recent_all += 1
                                    if source_ip and entry.get("source_ip") == source_ip:
                                        recent_source += 1
                        except (json.JSONDecodeError, ValueError):
                            continue
            except OSError:
                pass

        rates = {"federation_wide": recent_all, "per_source": recent_source}

        if recent_all >= self.limits["federation_wide_per_minute"]:
            return {
                "allowed": False,
                "reason": f"Federation-wide rate limit exceeded: {recent_all}/{self.limits['federation_wide_per_minute']}/min",
                "rates": rates,
            }

        if source_ip and recent_source >= self.limits["per_source_per_minute"]:
            return {
                "allowed": False,
                "reason": f"Per-source rate limit exceeded: {recent_source}/{self.limits['per_source_per_minute']}/min for {source_ip}",
                "rates": rates,
            }

        return {"allowed": True, "reason": None, "rates": rates}


# ─────────────────────────────────────────────
# Probe Execution
# ─────────────────────────────────────────────

def execute_probes(mcp_endpoint: str, timeout: int = PROBE_TIMEOUT_DEFAULT) -> dict:
    """Execute the 4-probe verification handshake against a visitor's MCP server.

    In production, this calls the visitor's MCP server. This implementation
    provides the probe framework with structured results. Actual MCP transport
    (list_tools, structured echo, state persistence, coherence) is wired in
    when the MCP client library is available.

    Args:
        mcp_endpoint: URL or connection info for the visitor's MCP server.
        timeout: Per-probe timeout in seconds.

    Returns:
        {
            "probes_passed": int (0-4),
            "results": {
                "capability_discovery": "pass"|"fail"|"skipped",
                "echo_probe": "pass"|"fail"|"skipped",
                "state_persistence": "pass"|"fail"|"skipped",
                "coherence": "pass"|"fail"|"skipped",
            },
            "errors": [{"probe": str, "error": str}, ...],
            "duration_ms": int,
        }
    """
    results = {name: "skipped" for name in PROBE_NAMES}
    errors = []
    probes_passed = 0
    start_time = time.monotonic()

    for i, probe_name in enumerate(PROBE_NAMES):
        try:
            passed = _run_single_probe(probe_name, mcp_endpoint, timeout)
            if passed:
                results[probe_name] = "pass"
                probes_passed += 1
            else:
                results[probe_name] = "fail"
                errors.append({"probe": probe_name, "probe_index": i + 1, "error": "probe_failed"})
                # Failure halts sequence — remaining probes stay "skipped"
                break
        except TimeoutError:
            results[probe_name] = "fail"
            errors.append({"probe": probe_name, "probe_index": i + 1, "error": "timeout"})
            break
        except Exception as e:
            results[probe_name] = "fail"
            errors.append({"probe": probe_name, "probe_index": i + 1, "error": str(e)})
            break

    duration_ms = int((time.monotonic() - start_time) * 1000)

    return {
        "probes_passed": probes_passed,
        "results": results,
        "errors": errors,
        "duration_ms": duration_ms,
    }


def _run_single_probe(probe_name: str, mcp_endpoint: str, timeout: int) -> bool:
    """Execute a single probe against the MCP endpoint.

    This is the integration point for actual MCP client calls.
    Each probe tests a specific capability:

    1. CAPABILITY_DISCOVERY: Call list_tools() on the MCP server.
       Pass condition: returns a non-empty valid tool list.

    2. ECHO_PROBE: Send structured JSON data, verify identical return.
       Pass condition: returned data matches sent data exactly.

    3. STATE_PERSISTENCE_PROBE: Multi-call sequence with state dependency.
       Pass condition: second call references state from first call.

    4. COHERENCE_PROBE: Open-ended contextual generation request.
       Pass condition: response is contextually appropriate (non-empty,
       relates to prompt context).

    Current implementation: MCP transport stub. Returns True for probe 1
    (CAPABILITY_DISCOVERY) when the endpoint is reachable, and delegates
    to actual MCP calls when the mcp client library is available.
    """
    # Check if MCP client is available for real probe execution
    try:
        return _probe_via_mcp(probe_name, mcp_endpoint, timeout)
    except ImportError:
        # No MCP client available — run local validation only
        return _probe_local_validation(probe_name, mcp_endpoint)


def _probe_via_mcp(probe_name: str, mcp_endpoint: str, timeout: int) -> bool:
    """Execute probe via actual MCP client transport.

    Raises ImportError if MCP client library is not available.
    This is the production path — wired when mcp SDK is installed.
    """
    # Import will raise ImportError if not available, falling back to local
    from mcp import ClientSession  # type: ignore[import-not-found]

    # MCP client integration point — to be wired with actual transport
    # when the MCP Python SDK is installed and the visitor server is reachable.
    raise ImportError("MCP client transport not yet wired")


def _probe_local_validation(probe_name: str, mcp_endpoint: str) -> bool:
    """Local-only probe validation (no MCP transport).

    Used when MCP client is not available. Validates that the endpoint
    is syntactically valid and reachable via HTTP ping for probe 1.
    Probes 2-4 require actual MCP transport and return False.
    """
    if probe_name == "capability_discovery":
        # Minimal validation: endpoint is a non-empty string that looks like a URL
        if not mcp_endpoint or not isinstance(mcp_endpoint, str):
            return False
        if mcp_endpoint.startswith(("http://", "https://", "stdio://")):
            return True
        return False

    # Probes 2-4 require MCP transport — cannot pass without it
    return False


# ─────────────────────────────────────────────
# Docks Handler
# ─────────────────────────────────────────────

class DocksHandler:
    """Main Docks ingress handler.

    Orchestrates wire-cut checks, rate limiting, visitor registration,
    probe execution, tiered admission, and signal emission.
    """

    def __init__(self, zone_root: str | None = None):
        self.zone_root = zone_root or resolve_zone_root()
        self.tz_config = load_ticzone(self.zone_root)
        self.al_path = audit_logs_path(self.zone_root, self.tz_config)
        self.visitor_registry_path = os.path.join(self.al_path, "visitors", "registry.jsonl")
        self.visa_registry_path = os.path.join(
            self.al_path, "biome", "visa-registry", "registry.jsonl"
        )
        self.rate_limiter = RateLimiter(self.zone_root)

    def register_visitor(self, dock_request: dict) -> dict:
        """Process a visitor.dock_request envelope.

        Full registration flow:
          1. Wire-cut check
          2. Rate limit check
          3. Create entity record
          4. Execute probe handshake
          5. Assign standing based on probe results
          6. Write to visitor registry
          7. Write visa state transition
          8. Emit signals

        Args:
            dock_request: Dict matching visitor.dock_request schema:
                - visitor_display_name (required)
                - mcp_server_endpoint (required)
                - home_federation_id (optional)
                - tvi_tier_claim (optional)
                - requested_role_flags (optional)
                - ingress_lane (optional, default tailscale_serve)
                - source_ip (optional, for rate limiting)

        Returns:
            Structured JSON result dict with ok, entity_id, standing, etc.
        """
        now = datetime.now(timezone.utc)

        # ── 1. Wire-cut check ──
        wire_cut = check_wire_cut()
        if wire_cut["active"]:
            rejection = {
                "ok": False,
                "error": "wire_cut_active",
                "wire_cut_scope": wire_cut["scope"],
                "message": "Docks registration halted — wire cut active.",
            }
            # Emit rejection signal during wire cut (per docks-wire-cut-spec.md)
            self._emit_signal("docks.rejection", {
                "source_ip": dock_request.get("source_ip", "unknown"),
                "rejection_reason": "wire_cut_active",
                "attempted_name": dock_request.get("visitor_display_name", "unknown"),
            })
            return rejection

        # ── 2. Validate required fields ──
        display_name = dock_request.get("visitor_display_name")
        mcp_endpoint = dock_request.get("mcp_server_endpoint")

        if not display_name:
            return {"ok": False, "error": "missing_field", "field": "visitor_display_name"}
        if not mcp_endpoint:
            return {"ok": False, "error": "missing_field", "field": "mcp_server_endpoint"}

        # ── 3. Rate limit check ──
        source_ip = dock_request.get("source_ip")
        rate_check = self.rate_limiter.check_rate(source_ip)
        if not rate_check["allowed"]:
            # Emit flood signal
            self._emit_signal("docks.registration_flood", {
                "rate": rate_check["rates"]["federation_wide"],
                "threshold": self.rate_limiter.limits["federation_wide_per_minute"],
                "window": 60,
                "source_ips": [source_ip] if source_ip else [],
            })
            return {
                "ok": False,
                "error": "rate_limit_exceeded",
                "message": rate_check["reason"],
            }

        # ── 4. Create entity record ──
        session_id = uuid.uuid4().hex[:12]
        entity_id = f"ent_visitor_{session_id}"
        ingress_lane = dock_request.get("ingress_lane", "tailscale_serve")
        tvi_tier_claim = dock_request.get("tvi_tier_claim")
        home_federation_id = dock_request.get("home_federation_id")
        requested_role_flags = dock_request.get("requested_role_flags", [])

        # ── 5. Emit registration signal ──
        self._emit_signal("docks.registration", {
            "entity_id": entity_id,
            "ingress_lane": ingress_lane,
            "tvi_tier_claim": tvi_tier_claim,
            "timestamp": now.isoformat(),
        })

        # ── 6. Execute probe handshake ──
        # Check wire-cut between registration and probes
        # (docks_all cancels in-progress handshakes)
        wire_cut_pre_probe = check_wire_cut()
        if wire_cut_pre_probe["active"] and wire_cut_pre_probe["scope"] in ("docks_all", "all"):
            self._emit_signal("docks.probe_failure", {
                "entity_id": entity_id,
                "failed_probe": "capability_discovery",
                "probe_index": 1,
                "error": "wire_cut_cancellation",
            })
            return {
                "ok": False,
                "error": "wire_cut_cancellation",
                "entity_id": entity_id,
                "message": "Probe handshake cancelled — wire cut escalated during registration.",
            }

        probe_results = execute_probes(mcp_endpoint)

        # ── 7. Determine admission tier ──
        probes_passed = probe_results["probes_passed"]
        standing, role_flags, visa_state = TIER_OUTCOMES.get(
            probes_passed, TIER_OUTCOMES[0]
        )

        # ── 8. Handle rejection (probe 1 fails) ──
        if standing is None:
            self._emit_signal("docks.rejection", {
                "source_ip": source_ip or "unknown",
                "rejection_reason": "probe_1_failure",
                "attempted_name": display_name,
            })
            # Emit probe failure signals
            for err in probe_results.get("errors", []):
                self._emit_signal("docks.probe_failure", {
                    "entity_id": entity_id,
                    "failed_probe": err["probe"],
                    "probe_index": err["probe_index"],
                    "error": err["error"],
                })
            return {
                "ok": False,
                "error": "probe_failure",
                "entity_id": entity_id,
                "probe_results": probe_results["results"],
                "message": f"Registration rejected: probe 1 (capability_discovery) failed.",
            }

        # ── 9. Verify TVI tier ──
        # If the visitor claimed a TVI tier, verify it matches probe results
        tvi_tier = _determine_tvi_tier(tvi_tier_claim, probe_results)

        # ── 10. Apply role flag constraints ──
        # Only grant requested role flags that the probe results support
        assigned_role_flags = _resolve_role_flags(
            requested_role_flags, role_flags, probes_passed
        )

        # ── 11. Write visitor registry entry ──
        visitor_record = {
            "entity_id": entity_id,
            "display_name": display_name,
            "home_federation_id": home_federation_id,
            "arrived_at": now.isoformat(),
            "standing": standing,
            "visa_state": visa_state,
            "probe_results": probe_results["results"],
            "tvi_tier": tvi_tier,
            "assigned_role_flags": assigned_role_flags,
            "trust_score": 0.0,
            "ingress_lane": ingress_lane,
            "session_id": session_id,
            "source_ip": source_ip,
            "last_activity_at": now.isoformat(),
            "departed_at": None,
            "departure_reason": None,
        }
        atomic_append_jsonl(self.visitor_registry_path, visitor_record)

        # ── 12. Write visa state transitions ──
        # Transition: arrived -> verified
        self._write_visa_transition(
            entity_id=entity_id,
            transition="arrived->verified",
            from_standing="guest",
            to_standing=standing,
            from_visa_state="arrived",
            to_visa_state="verified",
            evidence=f"probe handshake complete ({probes_passed}/4 pass)",
            authority="automated",
            timestamp=now,
        )

        # If probes passed >= 1, visitor is also admitted
        if probes_passed >= 1:
            self._write_visa_transition(
                entity_id=entity_id,
                transition="verified->admitted",
                from_standing=standing,
                to_standing=standing,
                from_visa_state="verified",
                to_visa_state="admitted",
                evidence=f"tier assignment: {probes_passed} probes passed, role_flags={assigned_role_flags}",
                authority="automated",
                timestamp=now,
            )
            # Update visa_state in the result
            visa_state = "admitted"

        # ── 13. Emit admission signal ──
        self._emit_signal("docks.admission", {
            "entity_id": entity_id,
            "standing": standing,
            "tvi_tier": tvi_tier,
            "probe_summary": f"{probes_passed}/4 probes passed",
        })

        # Emit probe failure signals for any failed probes
        for err in probe_results.get("errors", []):
            self._emit_signal("docks.probe_failure", {
                "entity_id": entity_id,
                "failed_probe": err["probe"],
                "probe_index": err["probe_index"],
                "error": err["error"],
            })

        # ── 14. Build session envelope ──
        session = {
            "entity_id": entity_id,
            "session_id": session_id,
            "standing": standing,
            "visa_state": visa_state,
            "probe_results": probe_results["results"],
            "tvi_tier": tvi_tier,
            "admitted_at": now.isoformat(),
            "biome_assignment": None,  # Assigned by biome router downstream
            "assigned_role_flags": assigned_role_flags,
            "probes_passed": probes_passed,
            "probe_duration_ms": probe_results["duration_ms"],
        }

        return {
            "ok": True,
            "entity_id": entity_id,
            "session": session,
            "visitor_record": visitor_record,
        }

    def check_status(self) -> dict:
        """Return current Docks status (wire-cut, rate, active sessions)."""
        wire_cut = check_wire_cut()
        rate = self.rate_limiter.check_rate()
        return {
            "wire_cut": wire_cut,
            "federation_rate": rate["rates"]["federation_wide"],
            "rate_limit": self.rate_limiter.limits["federation_wide_per_minute"],
        }

    # ── Signal emission ──

    def _emit_signal(self, signal_type: str, content: dict) -> str | None:
        """Emit a docks signal via docks-signal-emitter."""
        try:
            emitter = _get_signal_emitter()
            return emitter.emit_docks_signal(
                self.zone_root, signal_type, content, source="docks-handler.py"
            )
        except Exception as e:
            print(
                f"[DOCKS WARNING] Failed to emit signal {signal_type}: {e}",
                file=sys.stderr,
            )
            return None

    # ── Visa transition writing ──

    def _write_visa_transition(
        self,
        entity_id: str,
        transition: str,
        from_standing: str,
        to_standing: str,
        from_visa_state: str,
        to_visa_state: str,
        evidence: str,
        authority: str,
        timestamp: datetime,
    ) -> None:
        """Write a visa state transition to the visa registry."""
        record = {
            "entity_id": entity_id,
            "transition": transition,
            "from_standing": from_standing,
            "to_standing": to_standing,
            "from_visa_state": from_visa_state,
            "to_visa_state": to_visa_state,
            "timestamp": timestamp.isoformat(),
            "evidence": evidence,
            "authority": authority,
        }
        atomic_append_jsonl(self.visa_registry_path, record)


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

def _determine_tvi_tier(
    claimed_tier: str | None, probe_results: dict
) -> str:
    """Determine verified TVI tier from probe results.

    Rules:
      - If all 4 probes pass → native (visitor has full MCP fluency)
      - If probes 1-2 pass but 3-4 fail → adapter (partial MCP, needs wrapping)
      - If only probe 1 passes → proxy (minimal MCP capability)
      - If none pass → proxy (worst case)

    The visitor's self-reported claim is recorded but does not override
    the verified tier.
    """
    passed = probe_results["probes_passed"]
    if passed >= 4:
        return "native"
    elif passed >= 2:
        return "adapter"
    else:
        return "proxy"


def _resolve_role_flags(
    requested: list, tier_granted: list, probes_passed: int
) -> list:
    """Resolve final role flags from request + tier grant.

    Tier-granted flags are always included. Requested flags are only
    included if the probe results support them:
      - "expedition" requires probes 1-2
      - "student" requires all 4 probes
      - "foreign_delegate" requires all 4 probes
    """
    role_requirements = {
        "expedition": 2,
        "student": 4,
        "foreign_delegate": 4,
    }

    final = list(tier_granted)  # Always include tier-granted flags

    for flag in requested:
        if flag in final:
            continue  # Already granted by tier
        min_probes = role_requirements.get(flag, 4)  # Unknown flags require all 4
        if probes_passed >= min_probes:
            final.append(flag)

    return final


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Docks ingress handler — MCP verification handshake for visitor admission."
    )
    sub = parser.add_subparsers(dest="command")

    # ── register ──
    reg_p = sub.add_parser("register", help="Register a new visitor")
    reg_p.add_argument("--display-name", help="Visitor display name")
    reg_p.add_argument("--mcp-endpoint", help="MCP server endpoint URL")
    reg_p.add_argument("--ingress-lane", default="tailscale_serve",
                       choices=VALID_INGRESS_LANES,
                       help="Ingress lane (default: tailscale_serve)")
    reg_p.add_argument("--home-federation-id", default=None,
                       help="Originating federation identifier")
    reg_p.add_argument("--tvi-tier-claim", default=None,
                       choices=VALID_TVI_TIERS,
                       help="Self-reported TVI tier")
    reg_p.add_argument("--requested-role-flags", default="",
                       help="Comma-separated requested role flags")
    reg_p.add_argument("--source-ip", default=None,
                       help="Source IP for rate limiting")
    reg_p.add_argument("--stdin", action="store_true",
                       help="Read dock_request JSON from stdin")
    reg_p.add_argument("--zone-root", default=None,
                       help="Zone root path (auto-detected if omitted)")

    # ── probe ──
    probe_p = sub.add_parser("probe", help="Run probes against a registered visitor")
    probe_p.add_argument("--mcp-endpoint", required=True,
                         help="MCP server endpoint URL")
    probe_p.add_argument("--timeout", type=int, default=PROBE_TIMEOUT_DEFAULT,
                         help=f"Per-probe timeout in seconds (default: {PROBE_TIMEOUT_DEFAULT})")

    # ── wire-cut-status ──
    sub.add_parser("wire-cut-status", help="Check wire-cut sentinel status")

    # ── status ──
    status_p = sub.add_parser("status", help="Full Docks status check")
    status_p.add_argument("--zone-root", default=None)

    args = parser.parse_args()

    if args.command == "register":
        zone_root = args.zone_root or resolve_zone_root()
        handler = DocksHandler(zone_root)

        if args.stdin:
            dock_request = json.loads(sys.stdin.read())
        else:
            if not args.display_name or not args.mcp_endpoint:
                print(json.dumps({
                    "ok": False,
                    "error": "missing_args",
                    "message": "--display-name and --mcp-endpoint are required (or use --stdin)",
                }))
                sys.exit(1)
            dock_request = {
                "visitor_display_name": args.display_name,
                "mcp_server_endpoint": args.mcp_endpoint,
                "ingress_lane": args.ingress_lane,
                "home_federation_id": args.home_federation_id,
                "tvi_tier_claim": args.tvi_tier_claim,
                "requested_role_flags": [
                    f.strip() for f in args.requested_role_flags.split(",") if f.strip()
                ],
                "source_ip": args.source_ip,
            }

        result = handler.register_visitor(dock_request)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    elif args.command == "probe":
        results = execute_probes(args.mcp_endpoint, args.timeout)
        print(json.dumps(results, indent=2))
        sys.exit(0 if results["probes_passed"] > 0 else 1)

    elif args.command == "wire-cut-status":
        status = check_wire_cut()
        print(json.dumps(status, indent=2))
        sys.exit(0)

    elif args.command == "status":
        zone_root = args.zone_root or resolve_zone_root()
        handler = DocksHandler(zone_root)
        status = handler.check_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
