# Chapter 4: Bridge Inspector

**Human-Gated Review**

> Posture: OPS/META
>
> Time: ~20 minutes

---

*Find the bottleneck. Don't suppress the pressure. Relieve the structural constraint.*

---

## The scenario

You are the sole bridge inspector for Clearwater County. Seventeen bridges. One of you.

Every week, engineering firms submit proposals for bridge maintenance, upgrades, and repairs. The proposals arrive in your inbox as a queue. You review each one, stamp a verdict — approved, rejected, or edit requested — and move on.

The system works. For a while.

### The pile

Week 1: five proposals. You review all five. Two approved, two rejected, one sent back for edits. Clean inbox. Coffee is warm. Life is good.

Week 2: eight proposals. Three of them are resubmissions of last week's rejections — same firms, same bad load-bearing formulas, same wrong concrete ratios. You reject them again. Same reasons. Same annotations. Five new ones to review on top.

Week 3: fifteen proposals. Six of them are repeats. You start recognizing the handwriting. Engineering Firm A really believes in steel reinforcement for spans over 50 meters, and they will not stop proposing it no matter how many times you write "load formula incorrect for cantilever spans" in red ink.

Week 4: twenty-three proposals.

Week 5: forty-seven.

Week 8: one hundred and twenty-eight.

You are drowning. Not in bad proposals — in the *same* bad proposals. The pile isn't growing because the county has more bridges. It's growing because **your rejections carry no feedback**. The firms don't know *why* their proposals failed. They resubmit unchanged. You reject unchanged. The cycle spins.

### The feedback loop

Now imagine you change one thing: when you reject a proposal, you write a one-sentence annotation explaining why.

"Rejected — load formula uses static analysis; this span requires dynamic wind loading."

"Rejected — concrete mix ratio 1:2:4 is for foundations, not load-bearing pylons. Use 1:1.5:3."

"Rejected — steel reinforcement is appropriate for compression members, not the tension cables you've specified."

Week 1 with feedback: five proposals, same as before. But now the rejections carry reasons.

Week 2: six proposals. Only one resubmission — and it's been corrected. The firm read your annotation, fixed the formula, and resubmitted with dynamic wind loading. You approve it.

Week 3: four proposals. The repeat offenders are learning. Engineering Firm A finally stopped proposing steel reinforcement for tension cables.

Week 4: three proposals.

The pile isn't just shrinking. It's *compounding*. Every annotation you write prevents multiple future bad proposals. The feedback doesn't just help the immediate resubmission — it educates the submitter's model of what "good" looks like. Their future proposals arrive pre-improved.

This is the difference between a review queue and a review *system*. The queue processes items. The system shapes the quality of future items.

### The cost of feedback

Annotations take time. Writing "load formula incorrect" takes thirty seconds. That's thirty seconds you could spend reviewing the next proposal in the pile.

But the math works in your favor. One annotation now prevents three resubmissions later. Three prevented resubmissions free up ninety seconds of future review time. The investment compounds.

Without feedback: O(n) growing pile, where n increases every week.
With feedback: O(1) steady state, where quality improves every cycle.

The bottleneck was never the volume of proposals. It was the absence of feedback. Remove the constraint, and the pressure resolves itself.

---

## The warrant

While you've been inspecting bridges, something else has been happening.

Remember Mabel? The goat from Chapter 3? The one headbutting the PA microphone? The one emitting on PRIMITIVE with volume accruing at rate 5 per tick?

Check `fixtures/bridge_proposals.jsonl`. Scroll past the bridge proposals. Look at the last three entries.

```
sig_unknown_001 — BLEAT — volume 10  (tick 0)
sig_unknown_001 — BLEAT — volume 85  (tick 15)
wrn_mabel_001   — warrant — volume_threshold — "Trace origin. Identify handler gap."
```

Mabel's signal has been ticking since Chapter 1. Volume 10, then 15, then 20, then 25... fifteen ticks later, volume hit 85. Her `escalation_threshold` was 80.

**A warrant just fired.**

A warrant is not a suggestion. It's not an alert you can snooze. A warrant is a **governance obligation** — the system has determined that a signal has accrued enough pressure to demand human attention. Someone must trace the origin. Someone must act.

The warrant says: *"PRIMITIVE signal sig_unknown_001 (BLEAT) exceeded escalation threshold. Trace origin. Identify handler gap."*

Claude will trace it live.

### Trace the provenance

Where did `wrn_mabel_001` come from?

Follow the chain:

1. **This chapter** (Ch4): `wrn_mabel_001` was minted because `sig_unknown_001` crossed volume 80. Minting condition: `volume_threshold`. The warrant points at the signal.
2. **Chapter 3** (Zookeeper Radio): `sig_unknown_001` was revealed as Mabel's BLEAT. Band: PRIMITIVE. Source location: 0 (the PA speaker). Volume rate: 5 per tick. No handler configured for signal type BLEAT. She was received everywhere and processed nowhere.
3. **Chapter 2** (Dedup): The same content hash kept appearing — `BLEAT` with the same payload, new timestamps. Your dedup scanner flagged it as a recurring duplicate. Same identity, new instances.
4. **Chapter 1** (Append-Only): There it is. In the seed data. One line among the family calendar entries. An entry that didn't fit. `BLEAT`. The very first occurrence. This is where Mabel entered the system.

Four chapters. One goat. A signal that was stored (Ch1), deduplicated (Ch2), routed (Ch3), and escalated (Ch4) — all through the primitives you explored.

### The resolution

Here's the question the warrant forces you to answer: **what do you do about Mabel?**

Option A: Suppress the signal. Mark `sig_unknown_001` as expired. Set volume to zero. Mabel's BLEAT disappears from the system. The warrant clears. Your queue is clean.

Option B: Trace the root cause.

Mabel was never the problem. She's a goat. Goats headbutt things. That's what goats do. The PA microphone is at location 0. Mabel is at location 0. She headbutts the microphone. A PRIMITIVE signal is emitted. The signal is received by every listener in the zoo.

And then nothing happens. Because no handler is configured for signal type `BLEAT`.

The fix isn't to silence Mabel. The fix is to **register a handler**.

```python
register_handler("bridge_proposals.jsonl", "BLEAT", "route_to_petting_zoo_staff")
```

When a handler exists for `BLEAT`, matching signals are marked as `"processed"`. The signal still exists — Mabel is still headbutting the microphone, the BLEAT still propagates on PRIMITIVE — but now someone is *listening*. The petting zoo staff hears it, walks over, gives Mabel a scratch behind the ears, and life continues.

Volume drops to zero. Not because Mabel stopped. Because the system started *processing*.

**Constraint resolution, not suppression.** The pressure was never the problem. The missing handler was. You don't fix a fire alarm by cutting the wire. You fix it by responding to the fire.

Or in this case, the goat.

---

## See it in action

Claude will demo the review queue and warrant system:

- Submit 5 bridge proposals. Review them — two approved, three rejected without feedback. Watch the resubmissions pile up. The backlog grows because the rejections carry no information.
- Now reject WITH annotations: "load formula uses static analysis; this span requires dynamic wind loading." Watch the resubmission rate drop. The feedback compounds — each annotation prevents multiple future bad proposals.
- Trace `wrn_mabel_001` back through the provenance chain: warrant → escalated signal (volume 85) → original BLEAT (Chapter 1's seed data). Four chapters, one goat, one unbroken chain of evidence.
- Register a handler for signal type BLEAT. Mabel's signal is marked "processed" — not "expired." She isn't silenced. Someone is finally listening.

The tests prove each property. Claude runs them and walks you through the feedback economics and the warrant trace.

---

## What you're actually learning

You just saw a **feedback-driven review queue with provenance tracing and handler registration**.

The pieces:

1. **Review without feedback is a pile, not a pipeline.** A queue that only stamps pass/fail creates no back-pressure on input quality. The same bad proposals return forever. This is true of code review, alert triage, proposal assessment, and goat management.

2. **Feedback compounds.** One annotation prevents multiple future bad submissions. The investment is front-loaded (it takes time to write a good rejection reason) but the returns are exponential (fewer resubmissions, higher quality inputs, shrinking backlogs).

3. **Warrants are not alerts.** An alert says "something happened." A warrant says "something happened, it's been happening, it crossed a threshold, and now you are *obligated* to respond." Warrants carry provenance — you can trace them back to the original signal. They don't appear from nowhere. They are earned.

4. **Suppression is not resolution.** Silencing a signal removes it from your dashboard. Registering a handler removes it from your problem space. The signal still exists. The goat still bleats. But now someone is listening, and the system processes the signal instead of ignoring it. The constraint was the missing handler, not the signal volume.

5. **Provenance is the audit trail you'll need.** When a warrant fires, the first question is always "where did this come from?" If you can't trace it, you can't fix it. If you can trace it through four chapters of an academy tutorial, you can trace it through four layers of a production system.

---

## Understanding check

Questions Claude will explore with you:

- What's the difference between suppressing a signal and resolving its root cause?
- Why does feedback compound? (Think about what happens to the submitters' mental model.)
- A warrant says "trace origin, identify handler gap." Why trace instead of just fixing the immediate problem?
- Could you automate the review verdict? Should you? What would you lose?

---

## CGG connection

| Bridge/Zoo concept | CGG primitive | Where it lives |
|---|---|---|
| Proposal queue | CogPR (Cognitive Pull Request) | `<!-- --agnostic-candidate -->` tags |
| Review verdict (approve/reject/edit) | `/grapple` docket review | Plan Mode governance gate |
| Annotation feedback | CogPR `review_hints` + `rationale` | CPR metadata fields |
| Backlog pressure | Pending CPR count | `audit-logs/cprs/queue.jsonl` |
| Warrant auto-minting | Signal volume crosses `escalation_threshold` | `/siren tick` engine |
| `trace_warrant()` | Provenance chain via `source_signal_ids` | Warrant recognition engine |
| Handler registration | Signal processing pipeline | Handler configuration |
| Suppression vs resolution | Constraint resolution > silencing | Governance invariant |
| One-verdict-per-proposal | Idempotent review — same proposal reviewed once | Dedup on CPR lifecycle |
| Compounding feedback returns | Each `/grapple` review shapes future proposal quality | Human-gated review loop |

**The human gate is the value.** Automated systems can detect, route, escalate, and mint warrants. But the verdict — approve, reject, edit — is human. That's not a bottleneck. That's the design. The human doesn't review everything (that doesn't scale). The human reviews what the system *escalates* (that scales perfectly, because escalation is governed by volume thresholds and harmonic triads).

In CGG, `/grapple` is the human gate. It presents a docket of pending CogPRs and active warrants. The human reviews them. The verdicts flow back into the system as feedback. The quality of future proposals improves. The backlog stabilizes.

Sam would approve.

Mabel doesn't care about approval. She just wanted someone to listen.

---

Next chapter: [Graduation](../05-completion/README.md) — Full pipeline integration. All four postures. One certificate. Zero unexplained goat signals.
