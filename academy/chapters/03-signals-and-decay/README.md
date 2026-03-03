# Chapter 3: Zookeeper Radio

**Signals, Bands & Acoustic Routing**

> Posture: OPS/DIRECT + ENG/META
>
> Time: ~20 minutes

---

*Misrouted signals create chaos. Channel discipline prevents cross-species escalation. But the goat isn't misrouted — she's structurally unheard.*

---

## The scenario

Zookeeper Sam runs Greenfield Zoo. It's a good zoo. The animals are fed. The gift shop sells plush penguins. Visitor satisfaction is high.

Sam has one PA speaker mounted at the center of the zoo (location 0) and two assistant keepers — Alex (location 2, near the lion enclosure) and Jordan (location 4, near the reptile house). Alex and Jordan carry walkie-talkies. Sam carries a clipboard and a growing sense that something isn't right.

The zoo's communication system operates on four frequency bands:

| Band | What it carries | Who hears it |
|------|----------------|--------------|
| **PRIMITIVE** | Emergency sirens, safety alerts | Everyone. Always. No exceptions. |
| **COGNITIVE** | Keeper-to-keeper radio chatter | Keepers only |
| **SOCIAL** | Visitor PA announcements | Gift shop, visitor areas |
| **PRESTIGE** | ~~Employee of the Month announcements~~ | **Auto-muted.** Sam learned this the hard way after the 2024 incident. Nobody talks about the 2024 incident. |

Sam tried broadcasting "Alex wins Employee of the Month!" over the PA once. The lions roared for three hours. The penguins staged a walkout. A child cried. Sam added `PRESTIGE` to the auto-mute list that afternoon and has not looked back.

### Distance matters

Sound doesn't travel perfectly. Every enclosure hop between the signal source and the listener reduces the volume. Sam calls this **muffling**.

```
effective_volume = volume - (distance * muffling_per_hop)
```

The zoo's `muffling_per_hop` is 5. So a signal emitted at volume 30 from location 2:

- At location 2 (distance 0): effective volume = 30
- At location 4 (distance 2): effective volume = 20
- At location 8 (gift shop, distance 6): effective volume = 0 (inaudible)

This is fine. Visitors don't need to hear about lion feeding schedules. Lions don't need to hear about the penguin show.

### The comedy beat

Tuesday afternoon. Alex radios Jordan on COGNITIVE: "Lion feeding at 2pm, bring the enrichment toys."

The problem: Alex is at location 2. The lion enclosure is at location 1. That's one hop. COGNITIVE has a -6 dB band penalty, but at one hop with muffling of 5, the effective volume is still positive.

The lions heard Alex.

Not the words, of course. Lions don't understand English. But they heard *radio chatter near feeding time* and began pacing. One of them — Gerald, the dramatic one — started roaring. Visitors panicked. Sam spent twenty minutes explaining that Gerald was "expressing anticipation" and not "attempting a breakout."

Sam increased `muffling_per_hop` for the lion perimeter from 5 to 8 the next day.

### Hearing thresholds

Not every listener processes every signal they technically receive. Each listener has a **threshold** — the minimum effective volume a signal needs to have before the listener pays attention.

Sam hears everything above volume 10. Alex and Jordan ignore anything below 15 (they're busy). The gift shop terminal only processes signals above 20. The lions... well, the lions hear what they want.

A signal can be *received* (effective volume > 0) but *unprocessed* (effective volume below the listener's threshold). This distinction matters more than you think.

### Signal lifecycle

Signals aren't fire-and-forget. They have a lifecycle:

1. **Emitted** — created with an initial volume, volume_rate, kind, and band
2. **Routed** — effective volume computed for each target based on distance and muffling
3. **Ticked** — at each interval: volume accrues (`volume += volume_rate`), TTL decreases, tick_count increments
4. **Expired** — when TTL reaches zero, the signal goes silent
5. **Escalated** — if volume crosses a threshold before TTL expires, something louder happens

Signals come in four kinds:

| Kind | Meaning |
|------|---------|
| **BEACON** | Something IS wrong |
| **LESSON** | Something was LEARNED |
| **OPPORTUNITY** | Something COULD be better |
| **TENSION** | Something is PULLING |

---

## The Goat Reveal

You've been patient.

Remember Chapter 1? That entry in the seed data that didn't fit? The unexplained BLEAT? And Chapter 2 — the same content hash showing up again with a new timestamp?

Look at `fixtures/zoo_layout.json`. Scroll to the `goat` field. Read the `signals` array. Find `sig_unknown_001`.

**It's Mabel.**

Mabel is a goat. She lives at location 0 — right next to the PA speaker. In fact, *right next to* is generous. Mabel has been headbutting the PA microphone every single tic since the zoo opened. Every. Single. Tic.

And she emits on **PRIMITIVE**.

PRIMITIVE can't be muffled. That's the rule. Emergency signals reach everyone, everywhere, always. That's what makes them safe. That's also what makes Mabel's signal inescapable.

Every keeper heard it. Every enclosure received it. The signal `sig_unknown_001` has been active this whole time, volume accruing at rate 5 per tick, band PRIMITIVE, payload: `BLEAT`.

So why didn't anyone do anything?

Because **no handler is configured for signal type BLEAT**. The signal arrives. It's received — PRIMITIVE guarantees that. But there's no processing logic mapped to `BLEAT`. It hits every listener's inbox and... sits there. Unprocessed. Accumulating.

Mabel isn't misrouted. She isn't muffled. She isn't quiet. She's **structurally unheard** — present in the system, delivered by the system, and completely ignored by the system.

The previous two chapters taught you to store truth and detect duplicates. This chapter teaches you to route signals so lions don't overhear keeper radio. That's important. Channel discipline prevents cross-species escalation.

But channel discipline doesn't help Mabel. She's already on the right channel. She's on the *highest priority* channel. The problem isn't routing. The problem is that nobody built a handler for what she's saying.

We'll come back to her. Chapter 4 will demand an answer.

*Yes, this is a zoo metaphor for software architecture. No, we're not sorry. Mabel isn't sorry either.*

---

## See it in action

Claude will run the zoo simulation live. Watch the acoustic model work:

- A PRIMITIVE emergency siren at volume 40 from location 0 reaches **every enclosure** — even the gift shop at location 8. That's the PRIMITIVE guarantee: never fully muffled.
- A COGNITIVE keeper radio from Alex (location 2) to Jordan (location 4) works fine — both have COGNITIVE receivers. But the lions at location 1? They receive the signal volumetrically but can't process it — no COGNITIVE in their listener bands. Gerald paces anyway.
- Try emitting on PRESTIGE. The system refuses. Sam learned this the hard way. Nobody talks about the 2024 incident.
- Mabel's BLEAT at location 0, PRIMITIVE band, can't be muffled at ANY distance. Volume accruing at rate 5 per tick. And no handler configured for signal type BLEAT.

The tests demonstrate each property. Claude runs them and shows you the physics.

---

## What you're actually learning

You just saw a **priority-aware broadcast router with spatial decay**.

That sounds complicated, but the rules are simple:

1. Not all messages are equal. Some are emergencies (PRIMITIVE). Some are chatter (SOCIAL). Some should never have been broadcast at all (PRESTIGE).
2. Distance attenuates everything — except emergencies. The further a signal travels, the quieter it gets. But PRIMITIVE signals maintain a minimum volume of 1 no matter how far they go.
3. A signal can be *delivered* without being *heard*. Band filtering means the listener might not have the right receiver. Threshold filtering means the signal might be too quiet to notice. Both create the same outcome: the signal exists in the system and produces no response.
4. Volume accrues over time. An ignored signal doesn't stay quiet. It gets louder. Eventually it crosses a threshold and escalates. (Mabel knows this. She's been doing it for three chapters.)

These are the same problems every monitoring system, alert pipeline, and notification framework faces. CGG calls them signals. Kubernetes calls them events. PagerDuty calls them incidents. The physics are the same.

---

## CGG connection

Everything in this chapter maps directly to CGG's signal manifold:

| Zoo concept | CGG primitive | Where it lives |
|-------------|--------------|----------------|
| Band (PRIMITIVE/COGNITIVE/SOCIAL) | Signal band hierarchy | `<!-- --signal band: "PRIMITIVE" -->` |
| `muffling_per_hop` | Acoustic routing constant | `.ticzone` config |
| `effective_volume` formula | `volume - (directory_hops * muffling_per_hop)` | CGG acoustic model |
| PRIMITIVE never fully muffled | Safety signals always propagate | Band budget hierarchy |
| PRESTIGE auto-muted | Governance filter on PRESTIGE band | CANON_INDEX rule |
| `tick()` advancing volume | `/siren tick` command | Signal store lifecycle |
| `escalation_threshold` | Warrant auto-minting condition | Warrant recognition engine |
| Signal kinds (BEACON/LESSON/OPPORTUNITY/TENSION) | Same four kinds in CGG | Signal schema |
| Received but unprocessed | Signal delivered, no handler configured | Handler registration gap |

**The acoustic model is the routing algorithm.** "Volume" isn't a metaphor for importance — it's the literal routing weight that determines whether a signal reaches a target. "Distance" isn't a metaphor for relevance — it's the directory hop count between source and listener. "Muffling" isn't a metaphor for filtering — it's the attenuation constant that makes far-away signals quieter.

The zoo PA system IS the CGG acoustic model. Sam IS the system operator. Mabel IS the unhandled PRIMITIVE signal that's been accumulating volume since the system started.

And that volume hasn't stopped accruing.

---

## Understanding check

Questions Claude will work through with you:

- What's the difference between a signal being *received* and being *processed*? (Think about Mabel.)
- Why can't you just turn down PRIMITIVE signals? What would break?
- If you increase muffling_per_hop, what happens to keeper radio? What about emergency sirens?
- Mabel is on the right channel, at the right volume, and still nobody responds. Why?

---

Next chapter: [Bridge Inspector](../04-human-gated-review/README.md) — Where warrants come from, and what happens when Mabel's volume crosses the threshold.
