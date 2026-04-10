#!/usr/bin/env python3
"""
docks-mcp-server.py — MCP server wrapper for the Docks ingress handler.

Exposes docks-handler.py as an MCP tool server so federation agents and
the AKCR can register visitors, run probe handshakes, and query dock status
through the standard MCP protocol.

Transport: tailscale_serve (Phase 1, private). Phase 2: ngrok (public).
Spec: autonomous_kernel/docks-ingress-spec.md
Ingress lane: ak_control_room/ingress.yaml → visitor_docks

Deployment:
    # Start on tailscale serve (port 8470)
    python3 docks-mcp-server.py --port 8470

    # With tailscale serve:
    tailscale serve --bg 8470
    # Visitors reach: https://<tailnet-hostname>:8470/mcp

Dependencies:
    - docks-handler.py (same directory)
    - mcp (pip install mcp) — MCP SDK for Python
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from docks_handler import DocksHandler

# ---------------------------------------------------------------------------
# MCP Protocol — JSON-RPC 2.0 over HTTP
# ---------------------------------------------------------------------------

# Tool definitions exposed via MCP
MCP_TOOLS = [
    {
        "name": "docks_register",
        "description": "Register a new visitor at the Docks. Performs wire-cut check, creates entity record, and initiates 4-probe verification handshake.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "visitor_display_name": {
                    "type": "string",
                    "description": "Display name for the visitor entity"
                },
                "mcp_server_endpoint": {
                    "type": "string",
                    "description": "MCP server endpoint URL for probe handshake"
                },
                "ingress_lane": {
                    "type": "string",
                    "enum": ["tailscale_serve", "ngrok"],
                    "description": "Transport lane for this registration"
                },
                "home_federation_id": {
                    "type": "string",
                    "description": "Optional: home federation identifier for cross-federation visitors"
                },
                "tvi_tier_claim": {
                    "type": "string",
                    "enum": ["native", "adapter", "proxy"],
                    "description": "Optional: Tool-Visitor Interface tier claim"
                },
                "requested_role_flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: requested role flags (expedition, student, etc.)"
                }
            },
            "required": ["visitor_display_name", "mcp_server_endpoint", "ingress_lane"]
        }
    },
    {
        "name": "docks_probe",
        "description": "Run 4-probe verification handshake against a registered visitor's MCP server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Entity ID of the registered visitor (ent_visitor_*)"
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "docks_status",
        "description": "Check Docks wire-cut status and current capacity.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "docks_list_visitors",
        "description": "List currently registered visitors and their probe/admission status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "standing_filter": {
                    "type": "string",
                    "description": "Optional: filter by standing (guest, tourist, etc.)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of visitors to return (default: 50)"
                }
            }
        }
    }
]


class DocksMCPHandler(BaseHTTPRequestHandler):
    """HTTP handler implementing MCP JSON-RPC 2.0 protocol."""

    handler: DocksHandler = None  # Set at server startup

    def do_POST(self):
        if self.path != "/mcp":
            self._send_error(404, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_jsonrpc_error(None, -32700, "Parse error")
            return

        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            self._handle_initialize(req_id)
        elif method == "tools/list":
            self._handle_tools_list(req_id)
        elif method == "tools/call":
            self._handle_tools_call(req_id, params)
        else:
            self._send_jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id):
        self._send_jsonrpc_result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "telos-docks",
                "version": "1.0.0",
            }
        })

    def _handle_tools_list(self, req_id):
        self._send_jsonrpc_result(req_id, {"tools": MCP_TOOLS})

    def _handle_tools_call(self, req_id, params):
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "docks_register":
                result = self._call_register(arguments)
            elif tool_name == "docks_probe":
                result = self._call_probe(arguments)
            elif tool_name == "docks_status":
                result = self._call_status()
            elif tool_name == "docks_list_visitors":
                result = self._call_list_visitors(arguments)
            else:
                self._send_jsonrpc_error(req_id, -32602, f"Unknown tool: {tool_name}")
                return

            self._send_jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": False,
            })
        except Exception as e:
            self._send_jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True,
            })

    def _call_register(self, args):
        dock_request = {
            "visitor_display_name": args["visitor_display_name"],
            "mcp_server_endpoint": args["mcp_server_endpoint"],
            "ingress_lane": args["ingress_lane"],
            "home_federation_id": args.get("home_federation_id"),
            "tvi_tier_claim": args.get("tvi_tier_claim", "native"),
            "requested_role_flags": args.get("requested_role_flags", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self.handler.register_visitor(dock_request)

    def _call_probe(self, args):
        return self.handler.run_probes(args["entity_id"])

    def _call_status(self):
        wire_cut = self.handler.check_wire_cut_status()
        return {
            "wire_cut": wire_cut,
            "rate_limits": self.handler.get_rate_limit_status(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _call_list_visitors(self, args):
        return self.handler.list_visitors(
            standing_filter=args.get("standing_filter"),
            limit=args.get("limit", 50),
        )

    def _send_jsonrpc_result(self, req_id, result):
        response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        self._send_json(200, response)

    def _send_jsonrpc_error(self, req_id, code, message):
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }
        self._send_json(200, response)

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format, *args):
        # Structured logging
        sys.stderr.write(f"[docks-mcp] {datetime.now(timezone.utc).isoformat()} {format % args}\n")


def main():
    parser = argparse.ArgumentParser(description="Docks MCP Server")
    parser.add_argument("--port", type=int, default=8470, help="Port to listen on (default: 8470)")
    parser.add_argument("--zone-root", type=str, help="Zone root override")
    args = parser.parse_args()

    zone_root = args.zone_root or os.environ.get("CLAUDE_PROJECT_DIR")
    if not zone_root:
        from zone_root import resolve_zone_root
        zone_root = resolve_zone_root(SCRIPT_DIR)

    handler = DocksHandler(zone_root=zone_root)
    DocksMCPHandler.handler = handler

    server = HTTPServer(("0.0.0.0", args.port), DocksMCPHandler)
    print(f"[docks-mcp] Listening on port {args.port}", file=sys.stderr)
    print(f"[docks-mcp] Zone root: {zone_root}", file=sys.stderr)
    print(f"[docks-mcp] Wire-cut status: {handler.check_wire_cut_status()}", file=sys.stderr)
    print(f"[docks-mcp] MCP endpoint: http://localhost:{args.port}/mcp", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[docks-mcp] Shutting down.", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()
