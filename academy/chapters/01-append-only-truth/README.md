# Chapter 1: The Taylor Family Calendar

**Append-Only Truth**

> Posture: `OPS/DIRECT`
> Time: ~15 minutes
> Signal primitive: *Loud does not equal valid. Escalation does not equal understanding.*

---

## The scenario

Meet the Taylors. Five people, one shared calendar, and a scheduling system held together by sticky notes and group texts.

- **Mom (Sarah)** works Tuesdays and Thursdays, handles dentist appointments and grocery runs
- **Dad (Mike)** coaches Saturday soccer and is forever trying to sneak golf onto the calendar
- **Lily (14)** has piano on Wednesdays and a school play rehearsal schedule that changes weekly
- **Jake (11)** plays soccer (Mike's team) and has a new swim class signup
- **Emma (7)** goes wherever everyone else goes, which means her schedule is everyone else's schedule

Their problem is familiar to anyone who has shared a Google Calendar: Mike schedules golf for Saturday at 10am. Sarah already has Jake's soccer at Saturday 10am. Mike can't see Sarah's entry because he checked the calendar while his phone was on airplane mode. Now two events claim the same slot, and nobody knows which one wins until Saturday morning when Jake is standing in the driveway with cleats and Mike is holding a golf bag.

## What if nobody could delete anything?

Here is the rule that changes everything: **you can only add. Never edit. Never delete.**

Mike can't overwrite Sarah's dentist appointment. He can only append a new entry. If he wants to reschedule soccer, he appends a new soccer entry with the updated time. The old one stays. Both are visible. The *latest one wins*.

This sounds chaotic. It is the opposite of chaotic. Here is why:

1. **Full history.** Every scheduling decision ever made is preserved. When Jake asks "why did soccer move to 2pm?" you can show him the full trail of entries.
2. **No conflicts.** Concurrent writes to the same file never corrupt each other. Two parents can append at the same time -- you get two lines, not a mangled half-line.
3. **Accountability.** If Dad added golf over soccer, the evidence is right there. Append-only is a built-in audit trail.
4. **Simplicity.** The "database" is a text file. One JSON object per line. You can read it with `cat`.

The tradeoff? The file only grows. But for a family calendar -- or a governance signal store -- that growth IS the value. The history is the point.

## The format: JSONL

Each line is a standalone JSON object. No commas between them. No wrapping array. Just lines:

```json
{"id": "sat_soccer", "event": "Soccer practice", "who": "Jake", "day": "Saturday", "time": "10:00", "source": "sarah", "ts": "2026-02-28T18:00:00Z"}
{"id": "sat_soccer", "event": "Soccer practice", "who": "Jake", "day": "Saturday", "time": "14:00", "source": "sarah", "ts": "2026-03-01T09:00:00Z"}
```

Same `id`, two entries. The second one has a later timestamp. **Latest entry per ID wins.** The 10am soccer was real, then it moved to 2pm. Both facts are preserved. The current truth is the second line.

## See it in action

Claude will run the simulation for this chapter live. Watch what happens:

- When Dad appends his golf tee time, Mom's dentist appointment survives. Both entries coexist. That is append-only.
- When you ask "what is the current Saturday plan?" -- the latest entry for that ID wins. The history stays, but the current truth is clear.
- When two entries arrive at the same time from different sources, both land. No corruption, no conflict. POSIX append guarantees atomic writes below the pipe buffer size.

The tests prove each of these properties. Claude runs them and walks through what they demonstrate.

---

## What you are actually learning

You just saw the core data structure behind CGG's signal store.

In a real CGG installation, governance signals -- system health beacons, learning events, tension indicators -- are stored as JSONL files at `audit-logs/signals/YYYY-MM-DD.jsonl`. One file per day. Append-only. Latest-entry-per-ID-wins.

Why JSONL instead of a database?

- **Git-trackable.** The signal store lives in your repo. You can `git log` it. You can diff it. You can see exactly what changed and when.
- **Concurrent-write safe.** Two agents (or two parents) appending to the same file never corrupt each other. POSIX guarantees that appends below the pipe buffer size are atomic.
- **Zero dependencies.** No database server. No connection strings. No migrations. A text file and `json.loads`.
- **Full provenance.** Every state a signal has ever been in is preserved. When you need to understand *why* a warrant was minted, you read the full trail, not just the current state.

The Taylor family calendar is a governance signal store. The only difference is the payload.

> **CGG connection:** The `latest_by_id` logic -- scan every line, keep only the last occurrence of each ID, operate on the resolved state -- is the same read semantics used by `/siren tick` when it processes signal state. Your family calendar resolves "which soccer time is current" the same way CGG resolves "which signal state is current."

---

## About that last entry

Take a look at the bottom of `fixtures/seed_events.jsonl`. There is an entry that does not look like a family calendar event:

```json
{"id": "sig_unknown_001", "type": "signal", "kind": "BEACON", "payload": "BLEAT", "band": "PRIMITIVE", "volume": 10, "volume_rate": 5, "source": "???", "ts": "2026-03-01T08:00:00Z"}
```

Ignore that for now. We don't know what it is either.

---

## Understanding check

A couple things to think about -- Claude will ask you about these:

- If two people write to the same JSONL file at the exact same moment, what happens? (Hint: it is good news.)
- Why keep the old entries around? Why not just update in place?
- What is the difference between a database and a text file for governance signals?

---

**Next:** [Chapter 2 -- Did We Already Sign Up For That?](../02-dedup-and-identity/README.md)
