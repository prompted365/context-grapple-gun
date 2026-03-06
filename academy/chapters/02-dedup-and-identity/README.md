# Chapter 2: The Adjunct's Semester Project

**Collaboration Governance**

> Posture: `ENG/META`
> Time: ~20 minutes
> Signal primitive: *Patterns of coordination are governance-bearing. They are not soft extras.*

---

## The scenario

Professor Reyes teaches Introduction to Computer Science at Clearwater Community College. She uses the university's Anthropic instance for course administration, operating within university policy. Her students work in groups of four on semester-long projects -- this semester, they're building simple web applications.

The first round of group check-ins just happened. Reyes reviews the logs and notices a familiar pattern: some groups are thriving, others are struggling, and the differences have almost nothing to do with technical skill.

**Group A (The Clockwork Team)**:
- Weekly Wednesday standups, same time every week
- Clear role assignments: Alex handles frontend, Bailey does backend, Casey manages deployment, Dana writes documentation
- Attendance is tracked -- if someone misses, the others note it explicitly
- When Casey had a personal emergency week 3, they escalated to Reyes immediately
- Progress is steady. Everyone knows what everyone else is doing.

**Group B (The Chaos Team)**:
- "We'll meet when we need to" -- no fixed schedule
- No explicit roles -- everyone does everything, or tries to
- Two members haven't attended the last three ad-hoc meetings
- One member is doing 80% of the work and getting frustrated
- The others don't know about the frustration because nobody escalated anything
- They're technically on schedule, but barely, and it's fragile.

**Group C (The Silent Majority)**:
- They meet, but nobody takes notes
- They divide work, but nobody confirms who's doing what
- When someone falls behind, the others assume someone else will pick it up
- By week 6, three people thought someone else was handling the database layer
- Nobody was handling the database layer.

## What makes the difference?

Group A is not succeeding because they know more computer science. They're succeeding because they govern collaboration well.

They have:
- **Standing accountability structures** -- weekly check-ins that happen regardless of whether there's a crisis
- **Explicit role identity** -- clear ownership that prevents diffusion of responsibility
- **Attendance tracking** -- visible participation records so absence is noticed early
- **Early escalation protocols** -- a clear path to involve the professor before problems compound
- **Shared visibility** -- everyone knows the plan and the progress

These are not personality traits. These are patterns. And patterns can be learned, named, and taught.

## Collaboration patterns as governance material

Here is the key insight: **successful collaboration patterns are promotable governance artifacts**.

Group A's weekly standup habit is a pattern that could become a rule:
> "Hold a standing weekly check-in at a fixed time, regardless of perceived urgency. Consistent rhythm prevents invisible drift."

Group A's escalation protocol is a pattern that could become a rule:
> "Escalate to the project owner when a blocker persists more than 48 hours. Early escalation is cheaper than late recovery."

Group A's role clarity is a pattern that could become a rule:
> "At project start, assign explicit ownership of each major deliverable. Document assignments visibly."

These rules are not about web development. They are about how groups of humans (and agents) coordinate effectively. And they are just as valid as any technical rule about API design or database constraints.

## The scanner in action

Claude will demonstrate the collaboration pattern scanner:

- Review the group check-in log (`fixtures/group_checkins.jsonl`)
- Identify recurring patterns: attendance, role assignment, escalation events, milestone tracking
- Flag collaboration risks: silent members, diffused ownership, missed check-ins without escalation
- Surface promotable patterns: structures that appear in successful groups and could apply elsewhere

Watch for:
- How the scanner distinguishes healthy recurrence (regular check-ins) from problematic recurrence (repeated missed meetings)
- How patterns of coordination get fingerprinted and tracked
- How successful team structures become abstraction-ladder candidates

---

## What you are actually learning

You just saw **meta-learning** — learning about the conditions that make learning possible.

In Chapter 1, you learned to store truths about events. In this chapter, you learned that truths about collaboration are just as storable, just as promotable, and just as valuable.

CGG captures two classes of governance artifacts:

1. **Subject-matter lessons** — truths about the system being built
2. **Collaboration lessons** — truths about effective human-agent coordination

Both are valid CogPR candidates. Both can climb the abstraction ladder. Both are reviewed through the same constitutional gate.

Consider the theory-of-mind example from the root documentation:

An operator observed:
- Homeskillet was strong at structural reasoning
- Weaker when instructions depended on implicit assumptions
- Vulnerable to conceptual drift when prompts were under-scoped

So the operator started prompting with a theory-of-mind preface:
- What the agent is strong at
- Where the agent tends to drift
- Which assumptions must be explicit

That improved performance. After several cycles, the system surfaced it as a governance candidate:

> "When constructing subagent prompts, include a short theory-of-mind preface describing the agent's inferred strengths and limitations. This reduces conceptual drift and improves task alignment."

That is the same class of lesson as "hold standing weekly check-ins." Both are collaboration patterns. Both improve outcomes. Both are promotable.

## CGG connection

| Group project concept | CGG primitive | Where it lives |
|---|---|---|
| Weekly standup | Recurring cadence | Governance rhythm |
| Attendance tracking | Signal store | `audit-logs/signals/*.jsonl` |
| Role assignment | Ownership scope | CLAUDE.md jurisdiction |
| Escalation threshold | Warrant minting | Volume-triggered escalation |
| Missing member pattern | Recurring signal | Recurrence detection from Ch1 |
| Promotable team practice | CogPR candidate | `<!-- --agnostic-candidate -->` |
| Theory-of-mind preface | Collaboration lesson | Abstraction ladder |

**The key insight:** Collaboration patterns are governance artifacts.

Some groups succeed not because they know more, but because they govern coordination better. Successful collaboration structures can be recognized, captured, and promoted. They climb the same abstraction ladder as technical lessons.

---

## The BLEAT continues

Check the bottom of `fixtures/group_checkins.jsonl`. Something familiar:

```json
{"id": "sig_unknown_001", "type": "signal", "kind": "BEACON", "payload": "BLEAT", "band": "PRIMITIVE", "volume": 15, "source": "???", "ts": "2026-03-01T09:00:00Z"}
{"id": "sig_unknown_001", "type": "signal", "kind": "BEACON", "payload": "BLEAT", "band": "PRIMITIVE", "volume": 20, "source": "???", "ts": "2026-03-01T10:00:00Z"}
```

Same content fingerprint. Different timestamps. Your scanner from Chapter 1 would classify this as **recurring** -- not duplicate.

Something keeps happening. We still don't know what. But it's not noise.

---

## Understanding check

A few things Claude will explore with you:

- What's the difference between a personality trait and a learnable pattern?
- If "hold weekly standups" works for Group A, why might it fail for a different group? (Hint: patterns need context.)
- The theory-of-mind example describes adapting prompts to an agent's strengths. How would you apply that to briefing a new team member?
- Can a collaboration pattern ever be "wrong"? What would that look like?

---

**Previous:** [Chapter 1 -- The Taylor Family Calendar](../01-append-only-truth/README.md)
**Next:** [Chapter 3 -- Zookeeper Radio](../03-signals-and-decay/README.md)
