# Context Grapple Gun terminology

This glossary names the current public v5 concepts. Where internal runtime vocabulary is richer, the public term remains bounded by the definitions below.

## Authority states

**Born truth**  
A bounded observation or lesson exists on its originating surface. Born truth may be useful and accurate without yet carrying authority beyond that source.

**In-force truth**  
A rule, constraint, or operating instruction has passed the appropriate human review gate and now governs within its declared scope.

**Canonical source**  
The repository or constitutional file that expresses intended content and authority. Canonical source does not automatically become current behavior.

**Installed plugin**  
A plugin source registered by Claude Code at a named scope.

**Loaded runtime**  
The skills, agents, and hooks Claude Code actually loaded for current behavior. Loaded runtime is behavioral truth until installation, update, or verification changes it.

**Hydrated context**  
A working projection derived from authoritative sources for a current session. Visibility does not make the projection constitutional source.

## Lifecycle terms

**CogPR — cognitive or behavior pull request**  
A structured proposal asking whether a durable lesson should travel beyond its birth surface.

**Epoch**  
One bounded work interval whose end is made explicit rather than inferred from context loss.

**Cadence**  
The governed epoch-close operation. `/cadence` emits the canonical tic, seals the handoff, and leaves a resumable state. It does not own extraction, assessment, signal emission, or review judgment.

**Handoff**  
A bounded transfer carrying enough state, rationale, uncertainty, authority, and next motion for another session or actor to resume without forensic reconstruction.

**Hydration boundary**  
The distinction between authoritative source and the working context rendered from it.

**Receipt**  
An inspectable record of a state transition, including what changed, which authority applied, and what verification was performed.

## Governance terms

**Human constitutional gate**  
The named human authority that approves, modifies, defers, merges, supersedes, or rejects durable promotion.

**Abstraction ladder**  
The scope hierarchy through which a lesson may travel: Site → Domain → Estate → Federation → Global.

**Site**  
The current project or governance zone.

**Domain**  
A bounded subsystem or coherent functional area.

**Estate**  
Multiple projects under one operator or governing authority.

**Federation**  
Multiple estates participating under explicit interoperability and authority rules.

**Global**  
The operator-wide scope. Global is not granted by repetition, confidence, or directory depth.

**Zone**  
The project-local jurisdiction represented by `.ticzone`, `.ticignore`, audit history, and governing files.

**Tic**  
A sequenced timestamp used for canonical ordering. A tic is emitted by the cadence/clock authority, not inferred from raw row count when a stronger counter exists.

## Signal terms

**Signal**  
A persistent condition or recurring friction pattern tracked across time.

**Signal manifold**  
The governed collection of signals, relationships, thresholds, and current states.

**Warrant**  
A formal escalation minted when a governed signal predicate is satisfied. A warrant demands attention; it does not self-promote a law.

**Siren**  
The public signal-operations surface. `/siren` inspects and acts on signals without converting signal visibility into constitutional authority.

## Bands

**PRIMITIVE**  
Safety, survival, irreversible-harm, and data-integrity constraints.

**COGNITIVE**  
Learning, discovery, verified operating patterns, and process improvement.

**SOCIAL**  
Collaboration and coordination conditions, used narrowly.

**PRESTIGE**  
A governance-blocked classification/quarantine band. It is never activated as a normal project band and cannot mint authority merely through visibility.

## Distribution terms

**Source manifest**  
`.claude-plugin/plugin.json`, the complete component authority for direct Git plugin installation.

**Marketplace manifest**  
`.claude-plugin/marketplace.json`, which identifies plugin source and marketplace metadata. It does not carry a second partial component map.

**Package-pinned runtime**  
The exact CGG source included in a versioned npm package and copied to a durable target by the installer.

**Install receipt**  
`cgg-install-receipt.json`, which records package version, mode, scope, target, managed paths, verification evidence, and completion state.

**Install mode**  
The selected component surface: `full`, `skills`, or `convention`.

**Plugin scope**  
Claude Code registration scope: `user`, `project`, or `local`. Plugin scope does not change the project governance zone.

**Reconciliation**  
Comparison and governed repair between the invoked npm package, durable target, plugin registration, loaded inventory, and zone state.
