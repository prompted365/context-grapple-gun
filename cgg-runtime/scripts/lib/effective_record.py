#!/usr/bin/env python3
"""Deterministic third-surface correction resolver.

The append-only governance estate keeps authored records intact.  A later
``record_correction`` therefore cannot silently retcon its target; readers
need one shared fold:

    base record + ordered authorized corrections = effective record view

This module owns that fold.  It scans JSONL governance surfaces, validates the
canonical correction envelope, resolves supersession, preserves every branch
of lineage, and produces a deterministic derived index.  It never rewrites a
base record.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
CORRECTION_TYPE = "record_correction"
INDEX_RELATIVE = Path("corrections/effective-record-index.json")
BACKREFS_RELATIVE = Path("corrections/effective-record-backrefs.jsonl")
RECEIPTS_RELATIVE = Path("corrections/reconciliation-receipts.jsonl")
TRUSTED_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

IDENTIFIER_FIELDS = (
    "id",
    "record_id",
    "pass_id",
    "pass",
    "object_id",
    "emission_id",
    "mandate_id",
)
ACTIVE_STATES = {"authorized", "ratified"}
REVIEW_REQUIRED_STATES = {"proposed", "authorized"}
INACTIVE_STATES = {"superseded", "revoked"}
LIFECYCLE_STATES = ACTIVE_STATES | REVIEW_REQUIRED_STATES | INACTIVE_STATES
AUTHORITY_CLASSES = {
    "architect",
    "ratified_review",
    "maintainer",
    "system_migration",
}
CONSEQUENCE_CLASSES = {
    "informational",
    "interpretive",
    "operational",
    "publication_blocking",
}


@dataclass(frozen=True)
class LocatedRow:
    surface: str
    line: int
    value: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _legacy_migration_bindings() -> dict[tuple[str, str], set[str]]:
    """Load repository-controlled, exact legacy-row-to-correction bindings.

    Legacy action rows predate the typed correction contract and carry no
    canonical correction identifier.  A target/surface heuristic becomes
    ambiguous as soon as the same record receives another correction, so each
    admitted migration binds the immutable row digest and surface to one
    explicit correction ID.
    """
    bindings: dict[tuple[str, str], set[str]] = {}
    if not TRUSTED_MIGRATIONS_DIR.is_dir():
        return bindings

    for path in sorted(TRUSTED_MIGRATIONS_DIR.glob("*.json")):
        try:
            migration = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        binding = migration.get("legacy_binding")
        snapshot = migration.get("legacy_correction_snapshot")
        if not isinstance(binding, dict) or not isinstance(snapshot, dict):
            continue
        surface = binding.get("legacy_surface")
        declared_digest = binding.get("legacy_row_digest")
        correction_id = binding.get("canonical_correction_id")
        if not all(isinstance(value, str) and value for value in (
            surface,
            declared_digest,
            correction_id,
        )):
            continue
        if declared_digest != digest_value(snapshot):
            continue
        bindings.setdefault((surface, declared_digest), set()).add(correction_id)
    return bindings


def _trusted_correction_digests() -> set[str]:
    """Return corrections bound to packaged, repository-controlled receipts.

    A correction row's self-asserted lifecycle and authority strings are not
    evidence of admission.  The resolver applies an active correction only
    when an immutable copy and its digest-bound authorization receipt coexist
    in the managed runtime migration inventory.
    """
    trusted: set[str] = set()
    if not TRUSTED_MIGRATIONS_DIR.is_dir():
        return trusted

    for path in sorted(TRUSTED_MIGRATIONS_DIR.glob("*.json")):
        try:
            migration = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        correction = migration.get("canonical_correction")
        receipt = migration.get("canonical_authorization_receipt")
        provenance = migration.get("provenance")
        if not all(isinstance(value, dict) for value in (correction, receipt, provenance)):
            continue

        correction_digest = digest_value(correction)
        expected_receipt_path = f"cgg-runtime/migrations/{path.name}"
        append_commit = receipt.get("canonical_append_commit")
        valid_commit = (
            isinstance(append_commit, str)
            and len(append_commit) == 40
            and all(character in "0123456789abcdef" for character in append_commit)
        )
        if not all((
            receipt.get("schema_version") == SCHEMA_VERSION,
            receipt.get("type") == "record_correction_authorization_receipt",
            receipt.get("correction_id") == correction.get("correction_id"),
            receipt.get("correction_digest") == correction_digest,
            receipt.get("authority") == correction.get("authority"),
            receipt.get("lifecycle_state") == correction.get("lifecycle_state"),
            receipt.get("lifecycle_state") in ACTIVE_STATES,
            receipt.get("receipt_path") == expected_receipt_path,
            correction.get("receipt_path") == expected_receipt_path,
            receipt.get("canonical_append_repository") == provenance.get("repository"),
            append_commit == provenance.get("canonical_append_commit"),
            valid_commit,
        )):
            continue
        trusted.add(correction_digest)
    return trusted


def resolve_audit_root(zone_root: str | Path) -> Path:
    root = Path(zone_root).resolve()
    relative = "audit-logs"
    ticzone = root / ".ticzone"
    if ticzone.is_file():
        try:
            configured = json.loads(ticzone.read_text(encoding="utf-8"))
            relative = configured.get("audit_logs_path", relative)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    candidate = Path(relative)
    return candidate if candidate.is_absolute() else root / candidate


def _relative_surface(path: Path, zone_root: Path) -> str:
    try:
        return path.resolve().relative_to(zone_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _derived_paths(audit_root: Path) -> set[Path]:
    return {
        (audit_root / INDEX_RELATIVE).resolve(),
        (audit_root / BACKREFS_RELATIVE).resolve(),
        (audit_root / RECEIPTS_RELATIVE).resolve(),
    }


def discover_jsonl(zone_root: str | Path) -> list[Path]:
    root = Path(zone_root).resolve()
    audit_root = resolve_audit_root(root)
    if not audit_root.is_dir():
        return []
    excluded = _derived_paths(audit_root)
    return sorted(
        path for path in audit_root.rglob("*.jsonl")
        if path.resolve() not in excluded
    )


def source_digest(zone_root: str | Path, paths: Iterable[Path] | None = None) -> str:
    root = Path(zone_root).resolve()
    selected = list(paths if paths is not None else discover_jsonl(root))
    hasher = hashlib.sha256()
    for path in sorted(selected):
        data = path.read_bytes()
        _update_source_hasher(hasher, root, path, data)
    return hasher.hexdigest()


def _update_source_hasher(
    hasher: Any,
    root: Path,
    path: Path,
    data: bytes,
) -> None:
    surface = _relative_surface(path, root)
    hasher.update(surface.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(hashlib.sha256(data).digest())
    hasher.update(b"\0")


def record_identifiers(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for field in IDENTIFIER_FIELDS:
        value = row.get(field)
        if isinstance(value, str) and value and value not in values:
            values.append(value)
    return values


def is_correction(row: dict[str, Any]) -> bool:
    """Return true only for the canonical, typed correction envelope.

    Historical rows used ``action: record_correction`` before the v1 contract
    existed.  Treating those snapshots as v1 envelopes turns their expected
    missing fields into permanent validation failures.  They are tracked
    separately and must be paired with a typed migration instead.
    """
    return row.get("type") == CORRECTION_TYPE


def is_legacy_correction(row: dict[str, Any]) -> bool:
    return row.get("type") != CORRECTION_TYPE and row.get("action") == CORRECTION_TYPE


def _issue(code: str, message: str, **context: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **context}


def validate_correction(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the v1 canonical correction envelope.

    Semantic authorization is deliberately separate from JSON shape.  A row
    only gains effective-view authority in ``authorized`` or ``ratified``
    state and with an admitted authority class plus an authorization receipt.
    """
    issues: list[dict[str, Any]] = []

    required_strings = (
        "correction_id",
        "target_record_id",
        "target_surface",
        "literal_correction",
        "reason",
        "effective_at",
        "consequence_class",
        "lifecycle_state",
        "receipt_path",
    )
    if row.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("unsupported_schema", "schema_version must be 1"))
    if row.get("type") != CORRECTION_TYPE:
        issues.append(_issue("legacy_or_wrong_type", "type must be record_correction"))
    for field in required_strings:
        if not isinstance(row.get(field), str) or not row[field].strip():
            issues.append(_issue("missing_field", f"{field} must be a non-empty string", field=field))

    if not isinstance(row.get("effective_tic"), int) or row.get("effective_tic", -1) < 0:
        issues.append(_issue("invalid_effective_tic", "effective_tic must be a non-negative integer"))
    if not isinstance(row.get("patch"), dict) or not row.get("patch"):
        issues.append(_issue("invalid_patch", "patch must be a non-empty JSON Merge Patch object"))
    if not isinstance(row.get("supersedes"), list) or any(
        not isinstance(value, str) or not value for value in row.get("supersedes", [])
    ):
        issues.append(_issue("invalid_supersedes", "supersedes must be an array of correction ids"))
    if not isinstance(row.get("reversible"), bool):
        issues.append(_issue("invalid_reversible", "reversible must be boolean"))

    source = row.get("source")
    if not isinstance(source, dict):
        issues.append(_issue("invalid_source", "source must be an object"))
    else:
        for field in ("repository", "commit", "surface"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                issues.append(_issue("invalid_source", f"source.{field} is required", field=f"source.{field}"))

    authority = row.get("authority")
    if not isinstance(authority, dict):
        issues.append(_issue("invalid_authority", "authority must be an object"))
    else:
        for field in ("author_id", "authority_class", "authorization_ref"):
            if not isinstance(authority.get(field), str) or not authority[field].strip():
                issues.append(_issue("invalid_authority", f"authority.{field} is required", field=f"authority.{field}"))

    state = row.get("lifecycle_state")
    if isinstance(state, str) and state not in LIFECYCLE_STATES:
        issues.append(_issue("invalid_lifecycle_state", f"unsupported lifecycle_state: {state}"))
    consequence = row.get("consequence_class")
    if isinstance(consequence, str) and consequence not in CONSEQUENCE_CLASSES:
        issues.append(_issue("invalid_consequence_class", f"unsupported consequence_class: {consequence}"))
    return issues


def correction_is_authorized(row: dict[str, Any], trusted_digests: set[str]) -> bool:
    authority = row.get("authority") or {}
    return (
        row.get("lifecycle_state") in ACTIVE_STATES
        and authority.get("authority_class") in AUTHORITY_CLASSES
        and isinstance(authority.get("author_id"), str)
        and bool(authority.get("author_id"))
        and isinstance(authority.get("authorization_ref"), str)
        and bool(authority.get("authorization_ref"))
        and digest_value(row) in trusted_digests
    )


def apply_merge_patch(document: Any, patch: Any) -> Any:
    """Apply RFC 7396 JSON Merge Patch without mutating either input."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    result = copy.deepcopy(document) if isinstance(document, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            result[key] = apply_merge_patch(result.get(key), value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _order_key(correction: dict[str, Any]) -> tuple[int, str, str]:
    tic = correction.get("effective_tic")
    return (
        tic if isinstance(tic, int) else 2**63 - 1,
        str(correction.get("effective_at", "")),
        str(correction.get("correction_id", "")),
    )


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> list[str] | None:
        if node in visiting:
            start = trail.index(node)
            return trail[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        for parent in graph.get(node, []):
            cycle = visit(parent, trail + [parent])
            if cycle:
                return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for candidate in sorted(graph):
        cycle = visit(candidate, [candidate])
        if cycle:
            return cycle
    return None


def scan(zone_root: str | Path) -> dict[str, Any]:
    root = Path(zone_root).resolve()
    paths = discover_jsonl(root)
    bases: dict[tuple[str, str], list[LocatedRow]] = {}
    corrections: list[LocatedRow] = []
    legacy_corrections: list[LocatedRow] = []
    parse_issues: list[dict[str, Any]] = []
    source_hasher = hashlib.sha256()

    for path in paths:
        surface = _relative_surface(path, root)
        data = path.read_bytes()
        _update_source_hasher(source_hasher, root, path, data)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            parse_issues.append(_issue(
                "invalid_utf8", str(exc), surface=surface
            ))
            continue
        for line_number, raw in enumerate(text.splitlines(), 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                parse_issues.append(_issue(
                    "invalid_json", str(exc), surface=surface, line=line_number
                ))
                continue
            if not isinstance(row, dict):
                parse_issues.append(_issue(
                    "non_object_row", "JSONL rows must be objects", surface=surface, line=line_number
                ))
                continue
            located = LocatedRow(surface, line_number, row)
            if is_correction(row):
                corrections.append(located)
                continue
            if is_legacy_correction(row):
                legacy_corrections.append(located)
                continue
            for identifier in record_identifiers(row):
                bases.setdefault((surface, identifier), []).append(located)

    return {
        "zone_root": root,
        "audit_root": resolve_audit_root(root),
        "paths": paths,
        "source_digest": source_hasher.hexdigest(),
        "bases": bases,
        "corrections": corrections,
        "legacy_corrections": legacy_corrections,
        "parse_issues": parse_issues,
    }


def build_effective_index(zone_root: str | Path) -> dict[str, Any]:
    scanned = scan(zone_root)
    corrections = scanned["corrections"]
    legacy_corrections = scanned["legacy_corrections"]
    bases = scanned["bases"]
    unresolved: list[dict[str, Any]] = list(scanned["parse_issues"])
    trusted_correction_digests = _trusted_correction_digests()
    by_id: dict[str, LocatedRow] = {}
    duplicate_ids: set[str] = set()
    validation: dict[str, list[dict[str, Any]]] = {}

    for located in corrections:
        row = located.value
        correction_id = row.get("correction_id")
        key = correction_id if isinstance(correction_id, str) and correction_id else f"@{located.surface}:{located.line}"
        issues = validate_correction(row)
        source = row.get("source")
        source_surface = source.get("surface") if isinstance(source, dict) else None
        if isinstance(source_surface, str) and source_surface != located.surface:
            issues.append(_issue(
                "source_surface_mismatch",
                "correction row is not located on its declared source surface",
                declared_surface=source_surface,
                actual_surface=located.surface,
            ))
        if (
            row.get("lifecycle_state") in ACTIVE_STATES
            and digest_value(row) not in trusted_correction_digests
        ):
            issues.append(_issue(
                "unverified_authorization_receipt",
                "active correction is not bound to a repository-controlled authorization receipt",
                receipt_path=row.get("receipt_path"),
            ))
        validation[key] = issues
        if issues:
            unresolved.extend({**issue, "correction_id": key, "surface": located.surface, "line": located.line}
                              for issue in issues)
        if isinstance(correction_id, str) and correction_id:
            if correction_id in by_id:
                duplicate_ids.add(correction_id)
            else:
                by_id[correction_id] = located

    for correction_id in sorted(duplicate_ids):
        unresolved.append(_issue(
            "duplicate_correction_id",
            "correction_id appears more than once",
            correction_id=correction_id,
        ))

    legacy_migrations: list[dict[str, Any]] = []
    legacy_bindings = _legacy_migration_bindings()
    for located in legacy_corrections:
        legacy_target = located.value.get("corrects")
        row_digest = digest_value(located.value)
        bound_ids = sorted(legacy_bindings.get((located.surface, row_digest), set()))
        matches = [by_id[correction_id] for correction_id in bound_ids if correction_id in by_id]
        binding_mismatch = False
        if len(bound_ids) == 1 and len(matches) == 1:
            candidate = matches[0]
            source = candidate.value.get("source")
            source_surface = source.get("surface") if isinstance(source, dict) else None
            binding_mismatch = not (
                candidate.value.get("target_record_id") == legacy_target
                and source_surface == located.surface
            )
        if len(bound_ids) == 1 and len(matches) == 1 and not binding_mismatch:
            legacy_migrations.append({
                "legacy_surface": located.surface,
                "legacy_line": located.line,
                "legacy_row_digest": row_digest,
                "target_record_id": legacy_target,
                "canonical_correction_id": bound_ids[0],
                "binding_method": "exact_surface_and_canonical_row_digest",
                "status": "mapped",
                "disposition": "preserved_legacy_mapped_to_canonical",
            })
            continue
        if len(bound_ids) > 1:
            issue_code = "legacy_correction_ambiguous"
            issue_message = "legacy row digest has multiple explicit canonical bindings"
        elif binding_mismatch:
            issue_code = "legacy_correction_binding_mismatch"
            issue_message = "legacy binding points to a correction for another target or source surface"
        else:
            issue_code = "legacy_correction_unmigrated"
            issue_message = "legacy action:record_correction row has no resolvable explicit migration binding"
        issue = _issue(
            issue_code,
            issue_message,
            surface=located.surface,
            line=located.line,
            target_record_id=legacy_target,
            legacy_row_digest=row_digest,
            canonical_matches=bound_ids,
        )
        unresolved.append(issue)
        legacy_migrations.append({
            "legacy_surface": located.surface,
            "legacy_line": located.line,
            "legacy_row_digest": row_digest,
            "target_record_id": legacy_target,
            "canonical_correction_id": None,
            "status": "unresolved",
            "disposition": "preserved_legacy_unmigrated",
        })

    grouped: dict[tuple[str, str], list[LocatedRow]] = {}
    for located in corrections:
        row = located.value
        target_surface = row.get("target_surface")
        target_id = row.get("target_record_id")
        if isinstance(target_surface, str) and isinstance(target_id, str):
            grouped.setdefault((target_surface, target_id), []).append(located)

    records: list[dict[str, Any]] = []
    for target in sorted(grouped):
        target_surface, target_id = target
        target_corrections = sorted(grouped[target], key=lambda item: _order_key(item.value))
        target_bases = bases.get(target, [])
        local_unresolved: list[dict[str, Any]] = []
        for item in target_corrections:
            correction_id = item.value.get("correction_id")
            key = (correction_id if isinstance(correction_id, str) and correction_id
                   else f"@{item.surface}:{item.line}")
            local_unresolved.extend(
                {**issue, "correction_id": key, "surface": item.surface, "line": item.line}
                for issue in validation.get(key, [])
            )
        if not target_bases:
            issue = _issue(
                "orphan_correction",
                "target record does not exist on target_surface",
                target_record_id=target_id,
                target_surface=target_surface,
            )
            unresolved.append(issue)
            local_unresolved.append(issue)
            base = None
            base_location = None
        else:
            base_location = target_bases[-1]
            base = copy.deepcopy(base_location.value)

        target_ids = {
            item.value.get("correction_id")
            for item in target_corrections
            if isinstance(item.value.get("correction_id"), str)
        }
        graph: dict[str, list[str]] = {}
        for item in target_corrections:
            row = item.value
            cid = row.get("correction_id")
            if not isinstance(cid, str) or not cid:
                continue
            supersedes = row.get("supersedes", []) if isinstance(row.get("supersedes"), list) else []
            graph[cid] = [value for value in supersedes if isinstance(value, str)]
            for parent in graph[cid]:
                if parent not in target_ids:
                    issue = _issue(
                        "missing_superseded_correction",
                        "supersedes references a missing correction on this target",
                        correction_id=cid,
                        missing_correction_id=parent,
                    )
                    unresolved.append(issue)
                    local_unresolved.append(issue)
        cycle = _find_cycle(graph)
        if cycle:
            issue = _issue(
                "supersession_cycle",
                "correction supersession graph contains a cycle",
                target_record_id=target_id,
                cycle=cycle,
            )
            unresolved.append(issue)
            local_unresolved.append(issue)

        superseded_ids: set[str] = set()
        for item in target_corrections:
            row = item.value
            cid = row.get("correction_id")
            if not isinstance(cid, str) or validation.get(cid) or cid in duplicate_ids:
                continue
            if correction_is_authorized(row, trusted_correction_digests):
                superseded_ids.update(value for value in row.get("supersedes", []) if value in target_ids)

        effective = copy.deepcopy(base)
        lineage: list[dict[str, Any]] = []
        needs_review = False
        applied_ids: list[str] = []
        for item in target_corrections:
            row = item.value
            cid = row.get("correction_id")
            cid = cid if isinstance(cid, str) and cid else f"@{item.surface}:{item.line}"
            state = row.get("lifecycle_state")
            issues = validation.get(cid, [])
            disposition = "discarded_invalid"
            if issues or cid in duplicate_ids:
                disposition = "discarded_invalid"
            elif cid in superseded_ids or state == "superseded":
                disposition = "superseded"
            elif state == "revoked":
                disposition = "revoked"
            elif state == "proposed":
                disposition = "proposed_not_applied"
                needs_review = True
            elif (
                correction_is_authorized(row, trusted_correction_digests)
                and effective is not None
                and not local_unresolved
            ):
                effective = apply_merge_patch(effective, row["patch"])
                disposition = "applied_ratified" if state == "ratified" else "applied_pending_review"
                applied_ids.append(cid)
                if state == "authorized":
                    needs_review = True
            else:
                disposition = "discarded_unauthorized"
                needs_review = True

            lineage.append({
                "correction_id": cid,
                "effective_tic": row.get("effective_tic"),
                "effective_at": row.get("effective_at"),
                "lifecycle_state": state,
                "supersedes": row.get("supersedes", []),
                "disposition": disposition,
                "literal_correction": row.get("literal_correction"),
                "receipt_path": row.get("receipt_path"),
                "authority_receipt_verified": digest_value(row) in trusted_correction_digests,
            })

        records.append({
            "target_record_id": target_id,
            "target_surface": target_surface,
            "base_location": None if base_location is None else {
                "surface": base_location.surface,
                "line": base_location.line,
            },
            "base_record": base,
            "effective_record": effective,
            "differs": base is not None and effective != base,
            "applied_correction_ids": applied_ids,
            "lineage": lineage,
            "needs_review": needs_review,
            "unresolved": local_unresolved,
        })

    changed = [record for record in records if record["differs"]]
    review_required = [record for record in records if record["needs_review"]]
    index = {
        "schema_version": SCHEMA_VERSION,
        "type": "effective_record_index",
        "source_digest": scanned["source_digest"],
        "counts": {
            "source_files": len(scanned["paths"]),
            "correction_rows": len(corrections),
            "legacy_correction_rows": len(legacy_corrections),
            "mapped_legacy_corrections": sum(
                1 for migration in legacy_migrations if migration["status"] == "mapped"
            ),
            "target_records": len(records),
            "changed_records": len(changed),
            "review_required_records": len(review_required),
            "unresolved": len(unresolved),
        },
        "records": records,
        "legacy_migrations": legacy_migrations,
        "unresolved": sorted(unresolved, key=canonical_json),
    }
    index["index_digest"] = digest_value(index)
    return index


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_backrefs(index: dict[str, Any]) -> bytes:
    rows = []
    for record in index["records"]:
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "type": "record_correction_backref",
            "target_record_id": record["target_record_id"],
            "target_surface": record["target_surface"],
            "correction_ids": record["applied_correction_ids"],
            "effective_record_digest": digest_value(record["effective_record"]),
            "needs_review": record["needs_review"],
            "unresolved_codes": sorted({issue["code"] for issue in record["unresolved"]}),
        })
    if not rows:
        return b""
    return ("\n".join(canonical_json(row) for row in rows) + "\n").encode("utf-8")


def projection_status(zone_root: str | Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(zone_root).resolve()
    audit_root = resolve_audit_root(root)
    current = index or build_effective_index(root)
    index_path = audit_root / INDEX_RELATIVE
    backrefs_path = audit_root / BACKREFS_RELATIVE
    if not index_path.is_file():
        return {"exists": False, "stale": True, "reason": "missing_index"}
    try:
        stored = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"exists": True, "stale": True, "reason": "unreadable_index"}
    stored_digest = stored.get("index_digest")
    stored_without_digest = dict(stored)
    stored_without_digest.pop("index_digest", None)
    computed_stored_digest = digest_value(stored_without_digest)
    expected_backrefs = build_backrefs(current)
    expected_backrefs_digest = hashlib.sha256(expected_backrefs).hexdigest()

    reason = "current"
    if stored.get("source_digest") != current.get("source_digest"):
        reason = "source_digest_changed"
    elif stored_digest != computed_stored_digest:
        reason = "stored_index_digest_invalid"
    elif stored_digest != current.get("index_digest"):
        reason = "index_digest_changed"
    elif not backrefs_path.is_file():
        reason = "missing_backrefs"
    else:
        try:
            actual_backrefs_digest = hashlib.sha256(backrefs_path.read_bytes()).hexdigest()
        except OSError:
            reason = "unreadable_backrefs"
        else:
            if actual_backrefs_digest != expected_backrefs_digest:
                reason = "backrefs_digest_changed"

    stale = reason != "current"
    return {
        "exists": True,
        "stale": stale,
        "reason": reason,
        "stored_source_digest": stored.get("source_digest"),
        "current_source_digest": current.get("source_digest"),
        "stored_index_digest": stored_digest,
        "computed_stored_index_digest": computed_stored_digest,
        "current_index_digest": current.get("index_digest"),
        "expected_backrefs_digest": expected_backrefs_digest,
    }


def reconcile(
    zone_root: str | Path,
    *,
    authority: str,
    timestamp: str,
) -> dict[str, Any]:
    if not authority.strip():
        raise ValueError("authority is required for reconciliation writes")
    if not timestamp.strip():
        raise ValueError("timestamp is required for reconciliation receipts")

    root = Path(zone_root).resolve()
    audit_root = resolve_audit_root(root)
    index = build_effective_index(root)
    index_path = audit_root / INDEX_RELATIVE
    backrefs_path = audit_root / BACKREFS_RELATIVE
    receipts_path = audit_root / RECEIPTS_RELATIVE
    index_bytes = _json_bytes(index)
    backrefs_bytes = build_backrefs(index)
    projection = projection_status(root, index)
    changed = (
        projection["stale"]
        or not index_path.is_file()
        or index_path.read_bytes() != index_bytes
        or not backrefs_path.is_file()
        or backrefs_path.read_bytes() != backrefs_bytes
    )

    if changed:
        _atomic_write(index_path, index_bytes)
        _atomic_write(backrefs_path, backrefs_bytes)

    receipt_core = {
        "schema_version": SCHEMA_VERSION,
        "type": "effective_record_reconciliation_receipt",
        "source_digest": index["source_digest"],
        "index_digest": index["index_digest"],
        "backrefs_digest": hashlib.sha256(backrefs_bytes).hexdigest(),
        "authority": authority,
        "result": "reconciled",
        "unresolved": index["counts"]["unresolved"],
    }
    receipt_id = f"effective-record-{digest_value(receipt_core)[:20]}"
    receipt = {**receipt_core, "receipt_id": receipt_id, "timestamp": timestamp}

    existing_ids: set[str] = set()
    if receipts_path.is_file():
        for raw in receipts_path.read_text(encoding="utf-8").splitlines():
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(existing, dict) and isinstance(existing.get("receipt_id"), str):
                existing_ids.add(existing["receipt_id"])
    receipt_written = False
    if receipt_id not in existing_ids:
        receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(receipt) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        receipt_written = True

    return {
        "changed": changed,
        "result": "written" if changed else "already_current",
        "receipt_written": receipt_written,
        "receipt": receipt,
        "index_path": _relative_surface(index_path, root),
        "backrefs_path": _relative_surface(backrefs_path, root),
        "receipts_path": _relative_surface(receipts_path, root),
        "index": index,
    }


def review_gate(index: dict[str, Any]) -> dict[str, Any]:
    surfaced_records = [
        {
            "target_record_id": record["target_record_id"],
            "target_surface": record["target_surface"],
            "effective_record": record["effective_record"],
            "lineage": record["lineage"],
            "unresolved": record["unresolved"],
        }
        for record in index["records"]
        if record["differs"] or record["needs_review"] or record["unresolved"]
    ]
    hold = bool(
        index["unresolved"]
        or any(record["needs_review"] for record in index["records"])
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "consumer": "review",
        "status": "hold" if hold else "pass",
        "changed_records": index["counts"]["changed_records"],
        "review_required_records": sum(1 for record in index["records"] if record["needs_review"]),
        "unresolved": index["unresolved"],
        "records": surfaced_records,
        "source_digest": index["source_digest"],
    }


def hydration_view(index: dict[str, Any]) -> dict[str, Any]:
    affected_unresolved = {
        (record["target_surface"], record["target_record_id"])
        for record in index["records"] if record["unresolved"]
    }
    records = [
        {
            "target_record_id": record["target_record_id"],
            "target_surface": record["target_surface"],
            "base_location": record["base_location"],
            "effective_record": record["effective_record"],
            "applied_correction_ids": record["applied_correction_ids"],
        }
        for record in index["records"]
        if record["differs"]
        and (record["target_surface"], record["target_record_id"]) not in affected_unresolved
    ]
    blocked = bool(index["unresolved"])
    status = "blocked" if blocked else ("corrected" if records else "safe")
    return {
        "schema_version": SCHEMA_VERSION,
        "consumer": "hydration",
        "status": status,
        "effective_records": records,
        "blocked_targets": [
            {"target_surface": surface, "target_record_id": record_id}
            for surface, record_id in sorted(affected_unresolved)
        ],
        "unresolved": index["unresolved"],
        "source_digest": index["source_digest"],
    }
