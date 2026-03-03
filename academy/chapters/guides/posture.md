# The Four Postures

**Time: ~5 min**

Every chapter in this course declared a *posture* -- the quadrant you were working in. Posture is not a personality quiz. It is a scope declaration: are you analyzing or executing? Engineering or operating?

---

## The 2x2

| | DIRECT (execute) | META (analyze) |
|---|---|---|
| **ENG** | Implement, fix, ship code | Architect, plan, design |
| **OPS** | Run pipelines, hit APIs, generate artifacts | Audit outputs, review quality, explore |

Two axes. Four quadrants. One hard constraint.

### ENG/DIRECT -- Build the thing

You are writing code. You are fixing bugs. You are shipping features. Files change. Tests run. Git commits happen.

**Verbs:** fix, implement, build, patch, ship, wire, create

**Example:** "Fix the login form validation" -- you open the file, change the code, run the tests.

### ENG/META -- Design the thing

You are reading code. You are planning architecture. You are sketching data models. Nothing changes on disk. You are thinking about what to build, not building it.

**Verbs:** plan, design, architect, sketch, model, analyze

**Example:** "Plan the database schema for user profiles" -- you read existing schemas, draw relationships, propose a migration. No files written.

### OPS/DIRECT -- Run the thing

You are executing pipelines. You are calling APIs. You are generating artifacts. The system does work under your direction.

**Verbs:** run, execute, generate, deploy, trigger, call

**Example:** "Run the test suite and show me failures" -- you invoke `pytest`, read the output, report results.

### OPS/META -- Audit the thing

You are inspecting outputs. You are reviewing quality. You are exploring system state. Read-only reconnaissance.

**Verbs:** audit, review, explore, check, inspect, compare

**Example:** "Show me which signals have volume above 50" -- you read the signal store, filter, report. No mutations.

---

## The hard constraint

**META = read-only.** This is the one rule that matters.

In META posture (either ENG/META or OPS/META):
- No file edits or writes
- No git commit or push
- No destructive commands
- No API writes (POST/PUT/PATCH/DELETE)

If you are in META and an action would mutate state, pause first. Switch to DIRECT explicitly, or ask whether the mutation is intended.

DIRECT posture allows mutations -- but stays scoped to the specific files and systems being worked on.

---

## Verb inference

When posture is not explicitly declared, verbs determine the quadrant:

| DIRECT verbs | META verbs |
|---|---|
| fix, implement, build, generate, run, patch, ship | plan, design, analyze, audit, review, explore |

Mixed verbs in a single request (e.g. "take a look and fix") default to META. Analyze first, then switch to DIRECT for the fix.

---

## How each chapter used posture

| Chapter | Posture | Why |
|---------|---------|-----|
| 1 -- Taylor Family Calendar | **OPS/DIRECT** | You ran code against a JSONL file. Appending entries, reading state. Direct operations. |
| 2 -- Did We Already Sign Up? | **ENG/META** | You designed a hashing algorithm and classification scheme. Thinking about identity before writing the scanner. |
| 3 -- Zookeeper Radio | **OPS/DIRECT + ENG/META** | Mixed mode. You designed the acoustic model (META), then implemented routing functions and ran tick simulations (DIRECT). |
| 4 -- Bridge Inspector | **OPS/META** | You audited warrants, reviewed proposals, inspected evidence chains. Read-only judgment. |
| 5 -- Graduation | **ALL** | Full rotation. Phase 1 read back your code (ENG/META). Phase 2 wired the integration (ENG/DIRECT). Phase 3 ran the pipeline (OPS/DIRECT). Phase 4 audited the output (OPS/META). |

The course was designed to rotate through all four quadrants so that by Chapter 5 you had worked in each one.

---

## Practical examples

| Request | Posture | Reasoning |
|---------|---------|-----------|
| "Show me all errors in the last hour" | OPS/META | Inspecting system state. Read-only. |
| "Fix the login form" | ENG/DIRECT | Modifying code. Executing a fix. |
| "Run the test suite" | OPS/DIRECT | Executing a pipeline. Producing output. |
| "Plan the database schema" | ENG/META | Designing architecture. No mutations. |
| "Deploy to staging" | OPS/DIRECT | Executing infrastructure operations. |
| "Review the PR changes" | ENG/META | Analyzing code. Read-only inspection. |
| "Check the signal store for stale signals" | OPS/META | Auditing data. No modifications. |
| "Emit a BEACON for the failing health check" | OPS/DIRECT | Writing a signal. Mutating the signal store. |

---

## Posture in CGG

Posture is **advisory** in CGG. The CogPR format includes an optional `posture` field:

```
<!-- --agnostic-candidate
  posture: "ENG/META"
  ...
-->
```

This is metadata, not enforcement. It tells `/review` what mode the lesson was discovered in -- a lesson from active implementation (ENG/DIRECT) carries different weight than one from analysis (ENG/META).

However, substrates that *do* enforce constraints -- like the ecotone integrity gate or the META read-only rule -- use the same posture fields. If you later upgrade from advisory to enforced posture, there is zero schema migration. The fields are already there.

---

## Declaring posture

At the start of a session or when switching modes, a one-line declaration is enough:

```
POSTURE: ENG/DIRECT (reason: implementing the event store)
```

To switch mid-session:

```
[Posture -> OPS/META]
```

You do not need to declare posture for every action. Declare it when the mode changes or when the next step has side effects and the mode is ambiguous.
