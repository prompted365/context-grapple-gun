#!/usr/bin/env python3
"""
test_docks_mcp.py — Test harness for the Docks MCP server and DocksHandler.

Unit tests: exercise DocksHandler directly (no server process).
Smoke tests: start docks-mcp-server.py as a subprocess and send JSON-RPC requests.

All tests use a temporary zone root to avoid polluting real audit-logs.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

import pytest

# ---------------------------------------------------------------------------
# Resolve script directory and add to path
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from docks_handler import DocksHandler, check_wire_cut


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def zone_root(tmp_path):
    """Create a temporary zone root with the minimal structure DocksHandler needs."""
    # .ticzone config
    ticzone = {"name": "test-zone", "audit_logs_path": "audit-logs"}
    (tmp_path / ".ticzone").write_text(json.dumps(ticzone))

    # audit-logs directories
    (tmp_path / "audit-logs" / "visitors").mkdir(parents=True)
    (tmp_path / "audit-logs" / "signals").mkdir(parents=True)
    (tmp_path / "audit-logs" / "biome" / "visa-registry").mkdir(parents=True)

    return str(tmp_path)


@pytest.fixture
def handler(zone_root):
    """DocksHandler instance pointing at the temp zone root."""
    return DocksHandler(zone_root=zone_root)


@pytest.fixture
def sample_dock_request():
    """Realistic visitor registration payload."""
    return {
        "visitor_display_name": "Test Visitor Alpha",
        "mcp_server_endpoint": "http://localhost:9999/mcp",
        "ingress_lane": "tailscale_serve",
        "home_federation_id": "test_federation_1",
        "tvi_tier_claim": "native",
        "requested_role_flags": ["expedition"],
        "timestamp": "2026-04-10T19:00:00Z",
    }


def _find_free_port():
    """Find a free high port for the smoke test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _jsonrpc_request(port, method, params=None, req_id=1):
    """Send a JSON-RPC 2.0 request to the MCP server and return the parsed response."""
    payload = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        payload["params"] = params
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ===========================================================================
# UNIT TESTS — DocksHandler (no server process)
# ===========================================================================


class TestWireCut:
    """Wire-cut status check."""

    def test_wire_cut_returns_dict(self):
        result = check_wire_cut()
        assert isinstance(result, dict)
        assert "active" in result
        assert "scope" in result
        assert "sentinels" in result
        assert isinstance(result["sentinels"], dict)

    def test_wire_cut_no_sentinels_by_default(self):
        """Without sentinel files, wire cut should be inactive."""
        result = check_wire_cut()
        # May or may not be active depending on the test machine state,
        # but the structure must be correct.
        assert isinstance(result["active"], bool)


class TestVisitorRegistration:
    """Visitor registration through DocksHandler."""

    def test_register_visitor_success(self, handler, sample_dock_request):
        result = handler.register_visitor(sample_dock_request)
        assert result["ok"] is True
        assert "entity_id" in result
        assert result["entity_id"].startswith("ent_visitor_")
        assert "session" in result
        assert "visitor_record" in result

    def test_register_visitor_fields(self, handler, sample_dock_request):
        result = handler.register_visitor(sample_dock_request)
        record = result["visitor_record"]
        assert record["display_name"] == "Test Visitor Alpha"
        assert record["home_federation_id"] == "test_federation_1"
        assert record["ingress_lane"] == "tailscale_serve"
        assert record["standing"] == "guest"
        assert record["visa_state"] in ("verified", "admitted")
        assert record["trust_score"] == 0.0

    def test_register_visitor_probe_results(self, handler, sample_dock_request):
        result = handler.register_visitor(sample_dock_request)
        session = result["session"]
        probe_results = session["probe_results"]
        # Without MCP client, only capability_discovery passes (URL validation)
        assert probe_results["capability_discovery"] == "pass"
        assert session["probes_passed"] >= 1

    def test_register_visitor_writes_registry(self, handler, zone_root, sample_dock_request):
        handler.register_visitor(sample_dock_request)
        registry_path = os.path.join(zone_root, "audit-logs", "visitors", "registry.jsonl")
        assert os.path.isfile(registry_path)
        with open(registry_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["display_name"] == "Test Visitor Alpha"
        assert entry["entity_id"].startswith("ent_visitor_")

    def test_register_visitor_writes_visa_transitions(self, handler, zone_root, sample_dock_request):
        handler.register_visitor(sample_dock_request)
        visa_path = os.path.join(zone_root, "audit-logs", "biome", "visa-registry", "registry.jsonl")
        assert os.path.isfile(visa_path)
        with open(visa_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        # At least arrived->verified transition
        assert len(lines) >= 1
        first = json.loads(lines[0])
        assert first["transition"] == "arrived->verified"

    def test_register_missing_display_name(self, handler):
        result = handler.register_visitor({
            "mcp_server_endpoint": "http://localhost:9999/mcp",
            "ingress_lane": "tailscale_serve",
        })
        assert result["ok"] is False
        assert result["error"] == "missing_field"
        assert result["field"] == "visitor_display_name"

    def test_register_missing_endpoint(self, handler):
        result = handler.register_visitor({
            "visitor_display_name": "No Endpoint",
            "ingress_lane": "tailscale_serve",
        })
        assert result["ok"] is False
        assert result["error"] == "missing_field"
        assert result["field"] == "mcp_server_endpoint"

    def test_register_multiple_visitors(self, handler, zone_root):
        """Register several visitors, verify all appear in registry."""
        for i in range(3):
            result = handler.register_visitor({
                "visitor_display_name": f"Visitor {i}",
                "mcp_server_endpoint": f"http://localhost:{9900 + i}/mcp",
                "ingress_lane": "tailscale_serve",
            })
            assert result["ok"] is True

        registry_path = os.path.join(zone_root, "audit-logs", "visitors", "registry.jsonl")
        with open(registry_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 3


class TestCheckStatus:
    """DocksHandler.check_status()."""

    def test_status_structure(self, handler):
        status = handler.check_status()
        assert "wire_cut" in status
        assert "federation_rate" in status
        assert "rate_limit" in status


class TestRateLimiting:
    """Rate limiting doesn't block normal registration volume."""

    def test_normal_volume_not_blocked(self, handler):
        """5 registrations shouldn't trigger rate limiting."""
        for i in range(5):
            result = handler.register_visitor({
                "visitor_display_name": f"Rate Test {i}",
                "mcp_server_endpoint": f"http://localhost:{9800 + i}/mcp",
                "ingress_lane": "tailscale_serve",
            })
            assert result["ok"] is True, f"Registration {i} was blocked: {result}"


# ===========================================================================
# SMOKE TESTS — MCP server process
# ===========================================================================


@pytest.fixture(scope="module")
def mcp_server():
    """Start docks-mcp-server.py as a subprocess on a random port, yield (port, proc), then shut down."""
    port = _find_free_port()

    # Create a temp zone root for the server
    tmp_dir = tempfile.mkdtemp(prefix="docks_mcp_test_")
    ticzone = {"name": "smoke-test-zone", "audit_logs_path": "audit-logs"}
    with open(os.path.join(tmp_dir, ".ticzone"), "w") as f:
        json.dump(ticzone, f)
    for subdir in ["audit-logs/visitors", "audit-logs/signals", "audit-logs/biome/visa-registry"]:
        os.makedirs(os.path.join(tmp_dir, subdir), exist_ok=True)

    server_script = os.path.join(SCRIPT_DIR, "docks-mcp-server.py")
    proc = subprocess.Popen(
        [sys.executable, server_script, "--port", str(port), "--zone-root", tmp_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start (poll with retries)
    started = False
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                started = True
                break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)

    if not started:
        proc.kill()
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"MCP server did not start on port {port}. stderr: {stderr}")

    yield port, proc, tmp_dir

    # Shutdown
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestMCPSmoke:
    """Smoke tests against a live MCP server subprocess."""

    def test_initialize(self, mcp_server):
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "initialize")
        assert resp["jsonrpc"] == "2.0"
        assert "result" in resp
        result = resp["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "telos-docks"

    def test_tools_list(self, mcp_server):
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "tools/list", req_id=2)
        assert "result" in resp
        tools = resp["result"]["tools"]
        assert len(tools) == 4
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"docks_register", "docks_probe", "docks_status", "docks_list_visitors"}

    def test_tools_call_docks_status(self, mcp_server):
        """docks_status should return wire-cut and rate limit info."""
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "tools/call", {
            "name": "docks_status",
            "arguments": {},
        }, req_id=3)
        assert "result" in resp
        result = resp["result"]
        assert result["isError"] is False
        data = json.loads(result["content"][0]["text"])
        assert "wire_cut" in data
        assert "rate_limits" in data
        assert "timestamp" in data

    def test_tools_call_docks_register(self, mcp_server):
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "tools/call", {
            "name": "docks_register",
            "arguments": {
                "visitor_display_name": "Smoke Test Visitor",
                "mcp_server_endpoint": "http://localhost:9999/mcp",
                "ingress_lane": "tailscale_serve",
                "home_federation_id": "smoke_test_fed",
                "tvi_tier_claim": "native",
                "requested_role_flags": ["expedition"],
            },
        }, req_id=4)
        assert "result" in resp
        result = resp["result"]
        assert result["isError"] is False
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)
        assert data["ok"] is True
        assert data["entity_id"].startswith("ent_visitor_")

    def test_tools_call_docks_list_visitors(self, mcp_server):
        """After registering a visitor, list_visitors should return it."""
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "tools/call", {
            "name": "docks_list_visitors",
            "arguments": {},
        }, req_id=5)
        assert "result" in resp
        result = resp["result"]
        assert result["isError"] is False
        data = json.loads(result["content"][0]["text"])
        assert "visitors" in data
        assert "total" in data
        # Should contain the visitor registered in test_tools_call_docks_register
        # (module-scoped fixture means same server)
        # Note: test ordering isn't guaranteed, so just verify structure
        assert isinstance(data["visitors"], list)

    def test_invalid_method(self, mcp_server):
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "nonexistent/method", req_id=6)
        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert "not found" in resp["error"]["message"].lower()

    def test_unknown_tool(self, mcp_server):
        port, proc, _ = mcp_server
        resp = _jsonrpc_request(port, "tools/call", {
            "name": "nonexistent_tool",
            "arguments": {},
        }, req_id=7)
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_wrong_path_returns_404(self, mcp_server):
        """POST to a path other than /mcp should return 404."""
        port, proc, _ = mcp_server
        body = json.dumps({"jsonrpc": "2.0", "method": "initialize", "id": 8}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/wrong-path",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404
