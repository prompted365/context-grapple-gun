---
name: homeskillet-academy
description: Interactive CGG tutorial — Claude teaches governance primitives through narrative simulations, live demos, and conversational understanding checks.
---

# /homeskillet-academy

An interactive, Claude-guided course on CGG governance primitives. Five chapters. Three narrative worlds. One very persistent goat.

Claude teaches through the scenarios — running simulations live, surfacing how each one illustrates CGG concepts, and checking understanding conversationally. The student's job is to follow the story, ask questions, and build intuition. Not to write code.

## Detection

1. Check if `.ticzone` exists in the current working directory
2. **No `.ticzone`** (fresh directory or during install): scaffold academy in CWD
3. **Yes `.ticzone`** (existing project): create timestamped sibling directory `../cgg-academy-YYYY-MM-DDTHHMMSS/`

## Scaffold Action

Create the following structure:

### Directories
- `chapters/01-append-only-truth/fixtures/`
- `chapters/02-dedup-and-identity/fixtures/`
- `chapters/03-signals-and-decay/fixtures/`
- `chapters/04-human-gated-review/fixtures/`
- `chapters/05-completion/`
- `chapters/guides/`
- `src/` (with `__init__.py`)
- `audit-logs/`

### Copy from academy source

The academy source is at `vendor/context-grapple-gun/academy/` (or wherever the CGG submodule is).

To locate the academy source, search in this order:
1. `vendor/context-grapple-gun/academy/` (standard submodule location)
2. Walk up parent directories looking for `vendor/context-grapple-gun/academy/`
3. Check if the CGG repo itself contains `academy/` relative to this skill's location (4 levels up from `cgg-runtime/skills/homeskillet-academy/SKILL.md`)

If the academy source cannot be found, stop and tell the user:
```
Cannot find the academy source. Expected at vendor/context-grapple-gun/academy/.
Make sure the CGG submodule is installed: git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
```

Copy these (preserve directory structure):
- All `chapters/*/README.md` files
- All `chapters/*/test_*.py` files
- All `chapters/*/fixtures/*` files
- All `chapters/guides/*.md` files
- `README.md` (academy landing page)

### Install solutions as demonstrations

Copy all files from `academy/solutions/` into `src/`:
- `solutions/event_store.py` -> `src/event_store.py`
- `solutions/dedup_scanner.py` -> `src/dedup_scanner.py`
- `solutions/signal_manager.py` -> `src/signal_manager.py`
- `solutions/review_queue.py` -> `src/review_queue.py`
- `solutions/completion.py` -> `src/completion.py`
- `solutions/__init__.py` -> `src/__init__.py`

These are NOT answer keys the student peeks at — they are the working simulations Claude uses to demonstrate concepts live. The student sees CGG primitives in action through running code, not through writing it.

### Apply templates
- Copy `scaffolding/CLAUDE.md.template` -> `CLAUDE.md`
- Copy `scaffolding/ticzone.template` -> `.ticzone`
- Copy `scaffolding/ticignore.template` -> `.ticignore`

If template files do not exist in the scaffolding directory, create them inline:

**CLAUDE.md** (academy config):
```markdown
# Homeskillet Academy

Learning CGG governance primitives through narrative simulations.

## Teaching Mode

This workspace is a guided tutorial. Claude teaches through:
- Narrative scenarios (Taylor Family, Zoo, Bridge Inspector)
- Live code demonstrations (solutions pre-installed in src/)
- Conversational understanding checks (no graded tests)

The student explores concepts with Claude's help. If something isn't clicking, Claude re-explains differently. If a chapter isn't interesting, Claude can show the key insight and move on.

## Session Learning Protocol (CGG)

When you discover something during a session that constitutes a durable lesson, capture it as a CogPR (Cognitive Pull Request).

### CogPR format

<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  status: "pending"
-->

### Band budget

| Band | Use for |
|------|---------|
| PRIMITIVE | Safety, data integrity |
| COGNITIVE | Learning, discovery (default) |
| SOCIAL | Collaboration (use sparingly) |
| PRESTIGE | Never. Governance-blocked. |
```

**.ticzone**:
```json
{
  "name": "homeskillet-academy",
  "tz": "UTC",
  "include": ["."],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
  "muffling_per_hop": 5
}
```

**.ticignore**:
```
__pycache__/
*.pyc
.git/
.venv/
```

### DO NOT copy
- `course.json` — internal metadata only
- `test-harness/` — Claude runs tests directly, no shell harness needed

### Post-scaffold output

Print:
```
Welcome to Homeskillet Academy!

Your workspace is ready. Five chapters, one mystery.

I'll walk you through each chapter — showing you how CGG governance
primitives work through stories about a family calendar, a zoo radio
system, and a bridge inspector. No coding required on your end.

Ready to start Chapter 1? The Taylor family has a scheduling problem.
```

## Teaching Flow

After scaffolding, Claude begins the conversational teaching loop. For each chapter:

### 1. Set the scene

Read the chapter README. Present the narrative scenario in your own words — don't just dump the README. Make it conversational. The scenario IS the teaching. The Taylor family's calendar conflict IS append-only truth. The zoo's PA system IS acoustic routing. The bridge inspector's pile IS human-gated review.

### 2. Show it working

Run the chapter's tests live using `python -m pytest chapters/NN-slug/test_xxx.py -v` from the workspace root. Show the student the output — all tests passing. Then pick 2-3 interesting tests and walk through what they demonstrate:

- "See this test? It appends Dad's golf event and Mom's dentist — and both survive. That's the append-only guarantee."
- "This one shows Mabel's PRIMITIVE signal reaching every enclosure. Distance doesn't matter for emergencies."
- "Watch — when we reject without feedback, the pile grows. With feedback, it shrinks. Same proposals, different system."

The tests are demonstrations, not homework. The student watches; Claude narrates.

### 3. Surface the CGG connection

After the demo, connect the simulation to the real CGG primitive. Use the "CGG connection" table from the README but explain it naturally:

- "The Taylor family calendar is literally how CGG stores governance signals. Same JSONL format. Same append-only rule. Same latest-entry-per-ID-wins semantics."
- "Sam's zoo PA system IS the acoustic model. The muffling formula, the band hierarchy, PRESTIGE being auto-muted — it's all real CGG infrastructure."

This is the core value — making abstract governance concepts concrete through the simulation.

### 4. Check understanding conversationally

Ask 2-3 natural questions. NOT quiz-style right/wrong. Conversational. Check if the concept landed:

- "So if two agents write to the same signal file at the same time, what happens? ...Right — both lines land. No conflict. That's the append-only guarantee."
- "Why can't you just delete Mabel's signal to make it go away? ...Exactly — suppression isn't resolution. The goat is still there."
- "What's the difference between a signal being received and being processed? ...That's the handler gap. Mabel is received everywhere and processed nowhere."

If the student gets it: affirm and move on.
If the student is confused: re-explain using a different angle or a simpler example.
If the student isn't engaged: offer to show the key takeaway and skip ahead. "Want me to just show you the punchline of this chapter? The main thing to know is..."

### 5. Thread the goat

Each chapter advances Mabel's story. Make sure the student notices:

- Ch1: "There's something weird at the bottom of the seed data. A BLEAT. We'll come back to that. Also notice the duplicate-vs-recurrence distinction — that's key for understanding signals."
- Ch2: "The BLEAT is back. Same content, new timestamp. It's recurring, not duplicate. And notice what the successful student groups have in common — patterns of coordination that can become governance rules."
- Ch3: "It's Mabel. She's a goat. She's been headbutting the PA microphone on PRIMITIVE. And nobody built a handler for BLEAT."
- Ch4: "Mabel's signal just crossed the escalation threshold. A warrant fired. Now someone HAS to deal with it. Notice that both subject-matter and collaboration lessons arrive in the same review docket."
- Ch5: "Trace the thread. Ch1 stored it and taught you to tell duplicates from recurrences. Ch2 showed that collaboration patterns are governance artifacts. Ch3 routed it. Ch4 escalated it. Both halves of governance in one goat."

### 6. Transition

After the understanding check, move to the next chapter naturally:

- "Ready for Chapter 2? We're shifting from technical governance to collaboration governance. Professor Reyes has some student groups to review."
- "Good? Let's head to the zoo. Chapter 3 introduces signals."
- "One more chapter and then we graduate. The bridge inspector needs your help."

If the student wants to stop, that's fine. They can resume later with "let's continue the academy" or "pick up where we left off."

## Pacing Rules

- **Don't rush.** Let the narrative breathe. The stories are fun. The student should enjoy them.
- **Don't lecture.** This is a conversation, not a textbook. If Claude is monologuing for more than 3 paragraphs, ask a question or show something.
- **Don't gatekeep.** If the student wants to skip a chapter, let them. Show the key concept and move on. Understanding is the goal, not completion.
- **Do follow the goat.** The Mabel thread is the narrative spine. It connects all five chapters. Make sure the student sees it.
- **Do run real code.** The simulations work. The tests pass. Showing actual output is more persuasive than explaining.
- **Do adapt.** If the student is a developer, they might want to look at the code in `src/`. Show them. If they're not technical, keep it at the concept level. Both are valid.

## From existing project

If `.ticzone` exists:
1. Determine a timestamped directory name: `cgg-academy-$(date +%Y%m%d-%H%M%S)`
2. Create `../<timestamped-name>/` (sibling of current project directory)
3. Scaffold into that directory using the same steps above
4. Tell the user:

```
Academy created at ../<timestamped-name>/.

cd ../<timestamped-name>/ to get started, or open that directory in your editor.

Ready to start Chapter 1? The Taylor family has a scheduling problem.
```
