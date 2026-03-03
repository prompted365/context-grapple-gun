# Chapter 2: Did We Already Sign Up For That?

**Dedup & Identity**

> Posture: `ENG/META`
> Time: ~15 minutes
> Signal primitive: *Stewardship without root-cause mapping leaves latent instability.*

---

## The scenario

The Taylors have a new problem. The append-only calendar from Chapter 1 is working -- nobody can silently overwrite anyone else's entries. But now they are drowning in duplicates.

Here is what happened this week:

**Monday:** Sarah signed Jake up for swim class via the rec center website. Mike, not knowing Sarah already did it, signed Jake up from his phone using a different email. Two signups, same child, same class, same time slot. The rec center charged them twice.

**Tuesday:** Lily's school sent home a permission slip for the science museum field trip. Sarah signed it and emailed it back. Mike found the paper copy in Lily's backpack and also signed and emailed it. Then Lily's teacher, not seeing either response, sent a reminder -- and Sarah submitted a third time. Three permission slips. One field trip.

**Wednesday:** Sarah scheduled piano for Lily at 4pm. Then on Thursday, she rescheduled it to 5pm. That is NOT a duplicate -- it is a legitimate update. Same `id`, different content.

The problem is clear: the Taylors need to know when two entries *mean the same thing* even if they came from different sources. But they also need to tell the difference between "this is the same event submitted twice" and "this is the same event updated to a new time."

## Content-addressed hashing

The solution is older than computers. Instead of comparing entries field-by-field, you compute a fingerprint from the *content that matters*. If two entries produce the same fingerprint, they are semantically identical -- regardless of who submitted them, when, or from which email.

```python
import hashlib, json

def content_hash(event, keys):
    """Hash only the fields that define identity."""
    parts = [str(event.get(k, "")) for k in sorted(keys)]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

For the swim class, the identity keys might be `["event", "who", "day", "time"]`. Sarah's signup and Mike's signup produce the same hash because the content is identical -- only `source` and `ts` differ.

For the piano rescheduling, the hash changes because `time` changed from `"16:00"` to `"17:00"`. Same `id`, different content hash. That is an update, not a duplicate.

## Duplicate vs. recurring

Now here is a subtlety that matters more than it seems.

Two entries with the same content hash and the same timestamp? **Duplicate.** Somebody submitted the same thing twice.

Two entries with the same content hash but *different* timestamps? **Recurring.** The same thing happened again. That is not noise -- it might be a signal.

Think about it: if the dishwasher breaks on Monday and again on Thursday, the second report is not a duplicate of the first. It is a recurrence. A recurrence means the problem was not actually fixed. Dedup scanners that collapse recurrences into duplicates destroy information.

This distinction -- duplicate vs. recurring -- is one of the most important concepts in signal processing. Getting it wrong means either drowning in noise (treating recurrences as new) or losing signal (treating recurrences as duplicates).

## See it in action

Claude will demonstrate the dedup logic on the Taylor family data:

- Sarah and Mike's swim class signups produce the **same content hash** on identity keys -- same child, same class, same time slot. The system catches the double-booking.
- All three permission slip submissions hash identically. Three emails, one trip.
- Lily's piano reschedule produces a **different hash** because the time changed. That is an update, not a duplicate. The dedup scanner knows the difference.
- And those BLEATs? Same payload hash, different timestamps. The scanner classifies them as **recurring** -- not a duplicate. Something keeps happening.

The tests prove each distinction. Claude runs them and shows you the output.

---

## What you are actually learning

You just saw CGG's dedup engine in action.

When CGG processes signals, it uses content-addressed hashing to prevent the same insight from being recorded as multiple independent events. A CogPR (Cognitive Pull Request) discovered in one session should not generate a second CogPR if the same insight is discovered again in a later session.

But there is a critical wrinkle: **recurrence is not duplication.** If the same failure mode appears three weeks apart, that is not noise -- it is evidence that the root cause was never addressed. CGG's dedup logic preserves recurrences while collapsing true duplicates. The `classify_recurrence` logic is the core of that decision.

> **CGG connection:** The `content_hash` function mirrors `make_dedup_signal_id()` in CGG's signal emission pipeline. It takes a date, subsystem, and content hash to produce a deterministic signal ID. Same failure on the same day from the same subsystem produces the same ID -- preventing spam from repeated extension firings. But a new day means a new ID, allowing the signal to recur without being collapsed.

---

## That BLEAT again

Check the bottom of `fixtures/duplicate_events.jsonl`. Our mysterious friend is back:

```json
{"id": "sig_unknown_001", "type": "signal", "kind": "BEACON", "payload": "BLEAT", "band": "PRIMITIVE", "volume": 15, "volume_rate": 5, "source": "???", "ts": "2026-03-01T09:00:00Z"}
{"id": "sig_unknown_001", "type": "signal", "kind": "BEACON", "payload": "BLEAT", "band": "PRIMITIVE", "volume": 20, "volume_rate": 5, "source": "???", "ts": "2026-03-01T10:00:00Z"}
```

Different timestamps. Same content hash (on the identity keys). The dedup scanner classifies this as **recurring**, not a duplicate.

Something out there really wants to be heard.

---

## Understanding check

A couple things Claude will explore with you:

- If the same system failure happens on Monday and again on Thursday, is the Thursday report a duplicate? Why does the answer matter?
- What fields would you hash on to detect "same event, different source"? What about "same source, different event"?
- The BLEAT keeps recurring. What does that tell you about the underlying cause?

---

**Previous:** [Chapter 1 -- The Taylor Family Calendar](../01-append-only-truth/README.md)
**Next:** [Chapter 3 -- Zookeeper Radio](../03-signals-and-decay/README.md)
