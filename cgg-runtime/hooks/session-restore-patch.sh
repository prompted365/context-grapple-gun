#!/usr/bin/env bash
# CGG — Compatibility shim for session-restore-patch.sh
# Sources the canonical session-restore.sh entrypoint.
# Kept for backwards compatibility with existing plugin.json references.
CGG_HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$CGG_HOOK_DIR/session-restore.sh"
