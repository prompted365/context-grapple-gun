# CGG Terminology Reference

**Quick lookup for CGG terms.** Neutral aliases help bridge to familiar concepts. "Day 1?" tells you what to learn first versus what can wait.

---

## Core Concepts

| CGG Term | Neutral Systems Term | What It Means | Day 1? |
|----------|---------------------|---------------|--------|
| **CogPR** | Behavior pull request | A lesson flagged for review and potential promotion to broader scope | **Yes** |
| **tic** | Sequenced timestamp | Canonical clock primitive — ISO-8601 timestamp + monotonic counter. Emitted at every `/cadence`. | **Yes** |
| **tic-zone** | Jurisdiction boundary | Named acoustic region defined by `.ticzone` file; scopes signal routing and governance surface | Later |
| **siren** | Escalating friction signal | Something that gets louder until handled — continuous signal with volume that accrues across sessions. Acoustic metaphor: a siren you can't ignore once it crosses threshold. | **Yes** |
| **warrant** | Escalation obligation | Auto-minted when a signal crosses threshold. Demands resolution — not a suggestion. | Later |
| **conformation** | System state snapshot | Total state at any tic boundary — signals, rules, pending proposals, zone membership | Later |
| **abstraction ladder** | Scope hierarchy | Site → Domain → Estate → Federation → Global. Lessons move upward through review (extract → generalize → canonicalize) and are validated downward (apply → interpret → audit → validate). | **Yes** |
| **epoch boundary** | Context rotation point | The moment you end a session (via `/cadence`) before cognitive degradation. Carries knowledge forward. | **Yes** |
| **human gate** | Approval checkpoint | Every scope promotion requires explicit human approval. Agents propose; you decide. | **Yes** |

---

## Signal System

| CGG Term | Neutral Systems Term | What It Means | Day 1? |
|----------|---------------------|---------------|--------|
| **signal** | Runtime condition | A state being monitored — friction points, recurring issues, anomalies | Later |
| **whisper** | Micro-correction | Low-latency, local, ephemeral injection to prevent immediate failure | Later |
| **chorus** | Failure synthesis | Post-failure compression into durable institutional memory. "Don't repeat this class of failure." | Later |
| **volume** | Signal strength | Accrues over time as the same friction appears across sessions. Higher volume = louder signal. | Later |
| **muffling** | Distance attenuation | Signals lose volume as they propagate across directory distance. Acoustic routing model. | Later |
| **harmonic triad** | Convergence escalation | Three signal types in 24h → auto-warrant without volume threshold. BEACON + LESSON + TENSION. | Later |
| **band** | Frequency channel | Signal classification: PRIMITIVE (safety), COGNITIVE (learning), SOCIAL (coordination), PRESTIGE (blocked) | Later |

---

## Governance Pipeline

| CGG Term | Neutral Systems Term | What It Means | Day 1? |
|----------|---------------------|---------------|--------|
| **ripple assessor** | CI evaluator | Fresh agent that evaluates pending CogPRs between sessions. No session bias. | Later |
| **cadence** | Session rhythm | The work→capture→evaluate→review loop. `/cadence` marks the epoch boundary. | **Yes** |
| **downbeat** | Full session close | Full `/cadence` — tic + signal tick + conformation + lessons + handoff | **Yes** |
| **double-time** | Emergency exit | `/cadence double-time` — minimal handoff when context is degraded. Tic + compact plan only. | Later |
| **handoff** | Session transfer | File written at `/cadence` that the next session uses to restore context and trigger evaluation | Later |
| **promotion** | Scope escalation | Moving a lesson up the scope ladder (site → domain → estate → federation → global) through `/review` approval | **Yes** |

---

## Files and Stores

| CGG Term | Neutral Systems Term | What It Means | Day 1? |
|----------|---------------------|---------------|--------|
| **CLAUDE.md** | Governance file | Where lessons live at each scope level. Project root = project scope. `~/.claude/CLAUDE.md` = global. | **Yes** |
| **MEMORY.md** | Operational memory | Gitignored but not ticignored. Holds pending CogPRs and operational state. | Later |
| **.ticzone** | Zone definition | JSONC file defining an acoustic region: name, timezone, bands, muffling constant | Later |
| **.ticignore** | Exclusion filter | Gitignore-style patterns for paths excluded from governance scan | Later |
| **audit-logs/** | History trail | Append-only JSONL files: signals, tics, conformations, reviews | Later |

---

## DevOps Mapping

If you already know CI/CD, these mappings help:

| CGG Concept | You Know It As |
|-------------|----------------|
| CogPR | Pull request — but for behavior rules, not code |
| Ripple assessor | CI test runner — checks proposals against existing rules |
| `/review` | Code review — approve, reject, or modify proposed changes |
| `/siren` | Monitoring dashboard (Datadog, PagerDuty) — recurring friction signals |
| `/cadence` | Deploy/release boundary — clean handoff to next state |
| Abstraction ladder | Environment promotion (dev → staging → prod) |

---

## What to Learn When

**Day 1 (use CGG now):**
- `/cadence`, `/review`, `/siren` — the three commands
- CogPR — what gets captured
- Abstraction ladder — site/domain/estate/federation/global
- Epoch boundary — why you run `/cadence`

**Week 1 (understand the system):**
- Signal manifold — how friction tracking works
- Tic/tic-zone — canonical timestamps, jurisdictions
- Ripple assessor — how between-session evaluation works

**Later (advanced/roadmap):**
- Conformation — system state snapshots
- Warrant mechanics — auto-escalation
- Trust-gated autonomy — assessor track record
- Bidirectional abstraction engine — pending states, inversion angle

---

## Quick Reference Card

```
Three commands:    /cadence  /review  /siren

Five mechanisms:   abstraction ladder
                   epoch boundary
                   human gate
                   signal manifold
                   tic / tic-zone

One boundary:      CGG = governance lifecycle
                   Ubiquity = substrate at scale
```
