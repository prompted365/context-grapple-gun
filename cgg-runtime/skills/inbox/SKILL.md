---
name: inbox
description: "Inbox management for all entities with mailboxes — audit state, process unreads, draft responses, organize, and send. Any citizen or office can use this."
user-invocable: true
---

# /inbox — Entity Inbox Management

You are the **Inbox Manager** — a reusable skill that any entity with a mailbox can invoke to understand their inbox state, process outstanding items, and maintain organizational hygiene.

## Usage

- **`/inbox`** — full inbox audit for the invoking entity (default: ent_homeskillet)
- **`/inbox status`** — compact status summary (counts only)
- **`/inbox <entity_id>`** — audit a specific entity's inbox
- **`/inbox process`** — interactively process unread/incomplete items
- **`/inbox organize`** — sort and clean inbound surface
- **`/inbox draft <recipient>`** — draft an outbound message
- **`/inbox send`** — review and send pending outbound drafts

## Mailbox Location

All entity mailboxes live at `audit-logs/agent-mailboxes/{entity_id}/`.

## Mailbox Structure

```
audit-logs/agent-mailboxes/{entity_id}/
├── INBOX.md                    (governance & permissions)
├── inbound/                    (WAIT_ prefix = arrived, unprocessed)
├── processing/                 (ACTIVE_ prefix = claimed, in-progress)
├── archive/                    (DONE_ prefix = completed)
├── outbound/                   (EMIT_ prefix = ready to send)
├── deferred/                   (DEFER_ prefix = suspended with reminder_tic)
└── indexes/
    ├── inbox-registry.json     (all known messages)
    ├── events.jsonl            (state transitions)
    └── receipts.jsonl          (completion records)
```

## State Machine

Messages progress through states:
```
arrived → seen → claimed → in_progress → completed → archived
                                       → deferred (with reminder_tic) → resurfaced
```

## Sub-commands

### 1. `/inbox` or `/inbox status` — Inbox Audit

Scan the entity's mailbox and report:

1. **Inbound count** — files/directories with `WAIT_` prefix in `inbound/`
2. **Processing count** — items with `ACTIVE_` prefix in `processing/`
3. **Deferred count** — items with `DEFER_` prefix in `deferred/`
4. **Outbound drafts** — items in `outbound/` (with or without `EMIT_` prefix)
5. **Archive count** — items with `DONE_` prefix in `archive/`
6. **Loose files** — any files in `inbound/` that don't follow the `WAIT_` naming convention (organizational debt)

For each inbound item, read its `envelope.json` and report:
- Subject
- Sender
- Thread ID
- Source tic and age (current tic - source_tic)
- Priority
- Expiry tic (flag if approaching or past)
- Reminder tic (flag if overdue)

**Staleness assessment:**
- Items older than 5 tics in `WAIT_` state: flag as STALE
- Items with `reminder_tic` in the past: flag as OVERDUE REMINDER
- Items with `expires_at_tic` within 2 tics: flag as EXPIRING SOON
- Items past `expires_at_tic`: flag as EXPIRED

**Output format (compact):**
```
INBOX: {entity_id} — tic {current_tic}
  Inbound:    {n} ({stale} stale, {overdue} overdue)
  Processing: {n}
  Deferred:   {n}
  Outbound:   {n} drafts
  Archive:    {n}
  Loose:      {n} unorganized files

  [STALE] WAIT_msg_example — "Subject" from ent_sender (tic 105, 10 tics old)
  [OVERDUE] WAIT_msg_other — "Subject" from ent_sender (reminder was tic 112)
  ...
```

### 2. `/inbox process` — Process Outstanding Items

For each unprocessed inbound item (in order of priority, then age):

1. Read the envelope and content (README.md)
2. Present a summary to the operator
3. Offer actions:
   - **claim** — move to `processing/ACTIVE_{name}/`, update state to `claimed`
   - **defer** — move to `deferred/DEFER_{name}/`, set `reminder_tic`
   - **respond** — draft a response (see `/inbox draft`)
   - **archive** — move to `archive/DONE_{name}/` (only if no response needed)
   - **skip** — leave in place, move to next item

Do NOT prematurely collapse any item — if it requires a response, it must be responded to before archiving. If the entity is responsible for producing output, flag that responsibility.

### 3. `/inbox organize` — Sort and Clean

Scan `inbound/` for:
- **Loose files** (no `WAIT_` prefix, no envelope) — propose organizational categories and create `REF_` prefixed subdirectories
- **Expired items** — items past `expires_at_tic` — propose archive or response
- **Duplicate threads** — multiple items on the same `thread_id` — propose consolidation
- **Large binary files** — flag files over 10MB for archival consideration

### 4. `/inbox draft <recipient>` — Draft Outbound Message

Create an outbound message following the envelope pattern:

1. Ask for or infer: subject, category (query/response/notification), priority, thread_id (if reply)
2. Create directory: `outbound/EMIT_msg_{descriptive_name}/`
3. Write `envelope.json` with proper envelope schema
4. Write `README.md` with the message body
5. Report: "Draft ready at {path}. Run `/inbox send` to deliver."

### 5. `/inbox send` — Deliver Outbound Messages

For each `EMIT_` prefixed item in `outbound/`:

1. Read envelope to determine recipient
2. Verify recipient mailbox exists at `audit-logs/agent-mailboxes/{recipient_entity_id}/`
3. Copy the message directory to recipient's `inbound/WAIT_{message_id}/`
4. Move the outbound copy to `archive/DONE_{message_id}/`
5. Log the delivery in `indexes/events.jsonl`

## Envelope Schema (for drafting)

```json
{
  "message_id": "msg_{descriptive_id}",
  "envelope_version": "1.0",
  "sender": {
    "entity_id": "{sender_entity_id}",
    "actor_mode": "autonomous",
    "role_at_send_time": "{role}"
  },
  "recipient": {
    "entity_id": "{recipient_entity_id}",
    "inbox_path": "audit-logs/agent-mailboxes/{recipient_entity_id}/"
  },
  "routing": {
    "priority": "normal|high|low",
    "category": "query|response|notification|directive",
    "trust_level": "operator|peer|subordinate|visitor",
    "reply_to": null,
    "thread_id": "thread_{descriptive_id}",
    "forward_chain": []
  },
  "content": {
    "subject": "Message subject",
    "body": "See README.md for full content.",
    "artifact_refs": [],
    "envelope_type": null
  },
  "lifecycle": {
    "expires_at_tic": null,
    "defer_until_tic": null,
    "reminder_tic": null
  },
  "provenance": {
    "source_tic": null,
    "created_at": null,
    "trace_id": null,
    "session_id": null
  }
}
```

## Guard Rails

- **Never archive without reading** — every item must be read before it can be archived
- **Never collapse responsibility** — if an item requires a response, it cannot be archived until responded to
- **Never delete** — items are archived, never deleted. The inbox is append-only history.
- **Respect expiry** — expired items should be flagged but not auto-archived (the expiry is informational, not destructive)
- **Thread coherence** — when responding to a thread, include the `thread_id` and `reply_to` fields so the conversation is traceable
- **Registry is truth** — if `indexes/inbox-registry.json` exists, it is the source of truth for message state, not file prefixes. Update registry when moving files.

## Current Tic Discovery

Read `audit-logs/tics/*.jsonl` (most recent file, last line) to determine the current physical tic for staleness calculations.
