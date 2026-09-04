"""atomic_write.py — the one shared umask-honoring atomic file writer.

THE DEFECT THIS CURES
  bk-atomic-write-mkstemp-replace-drops-mode-to-0600 (standing ruling, tic 751;
  built /review 768 wave 6).

  `tempfile.mkstemp()` creates its temp file at 0600 BY DESIGN — that is the
  correct security default for a scratch file nobody else should read. But a
  writer that mkstemp()s a temp, writes it, and then `os.replace()`s it OVER a
  destination inherits the TEMP's mode, not the DESTINATION's. Every such
  rewrite silently downgrades the destination to owner-only. Nothing raises.
  Nothing logs. The drop is invisible until a reader with a different uid — a
  group-readable audit consumer, an export job, another account's tooling — is
  denied on a file that was readable yesterday.

  The failure has the shape the federation's Presence/Observation guard names:
  the write SUCCEEDS, the artifact IS present, and the permission truth
  degraded anyway. Presence is not correctness.

THE MODE POLICY (explicit, three-armed — this is the contract)
  mode=<int>   EXPLICIT WINS. The destination ends at exactly these permission
               bits. Use this when the artifact has a declared audience
               (0o644 for a shared/readable surface, 0o600 for a secret).

  mode=None    (the default) — two arms, decided by the destination:
    * destination EXISTS  -> PRESERVE its current permission bits.
      A REWRITE MUST NOT CHANGE WHO CAN READ A FILE. This is the arm that
      cures the defect: the replaced file keeps the mode it already had.
    * destination ABSENT  -> UMASK-DERIVED DEFAULT (0o666 & ~umask), i.e.
      byte-for-byte the mode a plain `open(path, "w")` would have produced.
      A new file created atomically is indistinguishable, permission-wise,
      from one created non-atomically.

HOW THE UMASK IS HONORED (and why the write path never calls os.umask)
  `os.umask()` has no read-only form: reading it means SETTING it and setting
  it back, a process-global read-modify-write that is neither thread-safe nor
  signal-safe. This module refuses that race on the write path. Instead the
  temp file is created with `os.open(..., O_CREAT | O_EXCL, 0o666)` and THE
  KERNEL applies the process umask at creation — which is precisely the
  definition of "umask-derived", obtained without ever mutating global state.
  `umask_default_mode()` below does use the read-restore idiom, but it is an
  INTROSPECTION helper (tests, receipts, diagnostics) and is never called by
  `atomic_write_bytes` / `atomic_write_text`.

  Consequence, stated plainly so it is not discovered later: while the temp is
  being written it carries the umask-derived mode (typically 0644), not 0600.
  That is the same exposure any ordinary `open(path, "w")` has. If the CONTENT
  is sensitive during the write window, pass an explicit `mode=0o600` — the
  temp is chmod'ed to the resolved mode before the replace, and callers that
  need secrecy must say so rather than inherit it by accident from mkstemp.

ATOMICITY
  Same-directory temp + `os.replace()` — atomic on POSIX within one
  filesystem. The temp is created in the DESTINATION'S directory (never
  /tmp), so the rename never crosses a device boundary. On any exception the
  temp is unlinked and the original destination is left untouched; a reader
  concurrent with the write sees either the old file or the new one, never a
  partial one.

STDLIB ONLY. No third-party imports, by fence.

USAGE
    from lib.atomic_write import atomic_write_text, atomic_write_bytes

    atomic_write_text(manifest_path, "".join(kept_lines))      # preserve mode
    atomic_write_bytes(index_path, index_bytes)                # preserve mode
    atomic_write_text(report_path, body, mode=0o644)           # declared mode

Both writers RETURN the mode actually applied, read back from the file
descriptor with fstat — a measured value, not an assumed one, so a caller or a
test can assert on what really landed instead of on what was intended.
"""

from __future__ import annotations

import os
import secrets
import stat
from typing import Optional, Union

__all__ = [
    "CREATE_MODE",
    "atomic_write_bytes",
    "atomic_write_text",
    "existing_mode",
    "resolve_target_mode",
    "umask_default_mode",
]

# Requested creation mode for the temp file. The kernel masks it with the
# process umask at O_CREAT, which is how the umask-derived default arm is
# honored without ever calling os.umask() on the write path.
CREATE_MODE = 0o666

# O_EXCL retry budget. A collision needs 8 random bytes AND the same pid AND
# the same instant; the budget exists so a pathological filesystem surfaces as
# a raised OSError rather than an unbounded loop.
_TEMP_ATTEMPTS = 16

PathLike = Union[str, "os.PathLike[str]"]


def existing_mode(path: PathLike) -> Optional[int]:
    """Permission bits of `path`, or None if it does not exist.

    Only FileNotFoundError/NotADirectoryError yield None. Any other OSError
    (EACCES on the parent, EIO) propagates: a destination we cannot stat is a
    destination we should not silently guess the mode of.
    """
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return None


def umask_default_mode() -> int:
    """0o666 & ~umask — the mode a plain `open(path, "w")` creates.

    INTROSPECTION ONLY. The write path does NOT call this; it lets the kernel
    apply the umask at O_CREAT instead.

    HAZARD, stated because it is real: os.umask() is a process-global
    read-modify-write with no read-only form. This function restores the prior
    value on the very next line, but the window is not thread-safe and not
    signal-safe. Do not call it in a hot loop or from a thread while another
    thread creates files.
    """
    current = os.umask(0o022)
    os.umask(current)
    return CREATE_MODE & ~current


def resolve_target_mode(path: PathLike, mode: Optional[int]) -> Optional[int]:
    """Decide the mode to apply, per the three-armed policy in the docstring.

    Returns an explicit int to chmod to, or None meaning "leave the temp at the
    kernel's umask-derived creation mode" (the destination-absent arm).
    """
    if mode is not None:
        return mode
    return existing_mode(path)


def _open_new_temp(directory: str, prefix: str) -> "tuple[int, str]":
    """Create a fresh temp file in `directory` at CREATE_MODE & ~umask.

    O_EXCL makes the create race-safe without mkstemp's 0600 clamp.
    """
    last_exc: Optional[OSError] = None
    for _ in range(_TEMP_ATTEMPTS):
        candidate = os.path.join(
            directory, f"{prefix}{os.getpid()}.{secrets.token_hex(8)}.tmp"
        )
        try:
            fd = os.open(
                candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, CREATE_MODE
            )
        except FileExistsError as exc:  # pragma: no cover - needs a collision
            last_exc = exc
            continue
        return fd, candidate
    raise OSError(
        f"atomic_write: could not create a unique temp in {directory!r} after "
        f"{_TEMP_ATTEMPTS} attempts"
    ) from last_exc


def atomic_write_bytes(
    path: PathLike,
    data: bytes,
    *,
    mode: Optional[int] = None,
    fsync: bool = True,
    make_parents: bool = True,
) -> int:
    """Atomically write `data` to `path`. Returns the mode actually applied.

    mode=None preserves an existing destination's permission bits and falls
    back to the umask-derived default for a new file. See the module docstring
    for the full policy.
    """
    target = os.fspath(path)
    directory = os.path.dirname(target) or "."
    if make_parents:
        os.makedirs(directory, exist_ok=True)

    resolved = resolve_target_mode(target, mode)
    fd, temporary = _open_new_temp(directory, f".{os.path.basename(target)}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
            if resolved is not None:
                os.fchmod(handle.fileno(), resolved)
            applied = stat.S_IMODE(os.fstat(handle.fileno()).st_mode)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:  # pragma: no cover - best-effort cleanup
            pass
        raise
    return applied


def atomic_write_text(
    path: PathLike,
    text: str,
    *,
    mode: Optional[int] = None,
    encoding: str = "utf-8",
    fsync: bool = True,
    make_parents: bool = True,
) -> int:
    """Text convenience over atomic_write_bytes. Returns the applied mode.

    Encodes directly rather than opening in text mode: on POSIX this is
    byte-identical to `open(p, "w", encoding=...)` output (newline=None
    translates "\\n" to os.linesep, which is "\\n"), and it keeps exactly one
    code path for the atomic replace.
    """
    return atomic_write_bytes(
        path,
        text.encode(encoding),
        mode=mode,
        fsync=fsync,
        make_parents=make_parents,
    )
