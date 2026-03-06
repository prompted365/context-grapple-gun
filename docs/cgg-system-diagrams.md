# CGG System Diagrams

Portable system architecture diagrams for Context Grapple Gun v3.

Actor names in these diagrams (Mogul, Homeskillet, Swann) are estate-specific
instantiations of CGG's generic roles: suborchestrator, UX plane, clock authority.

## 1. Signal Lifecycle Flow

```mermaid
flowchart TD
    subgraph Emission
        E1[Session event / hook detection]
        E2[Signal emitted to audit-logs/signals/YYYY-MM-DD.jsonl]
        E1 --> E2
    end

    subgraph Accrual
        A1{Kind warrant-eligible?<br/>BEACON or TENSION}
        A2[Volume accrues per tic<br/>volume += volume_rate]
        A3[Acoustic decay per tic<br/>volume -= decay_rate_per_tic<br/>if unreinforced]
        A4[LESSON/OPPORTUNITY:<br/>routes to CPR pipeline]
        E2 --> A1
        A1 -->|Yes| A2
        A1 -->|No| A4
        A2 --> A3
    end

    subgraph Resolution
        W1{Volume >= warrant_threshold<br/>OR harmonic triad?}
        W2[Warrant minted]
        W3[Human review via /review]
        W4[Terminal: resolved or dismissed]
        A3 --> W1
        W1 -->|Yes| W2
        W1 -->|No| A2
        W2 --> W3
        W3 --> W4
    end

    subgraph PrimitiveFloor["PRIMITIVE Band Floor"]
        PF[effective_volume =<br/>max computed hearing_threshold + 1]
    end

    A3 -.->|PRIMITIVE band| PF
```

## 2. Mandate Execution Sequence

```mermaid
sequenceDiagram
    participant T as Trigger<br/>(hook/skill/cadence)
    participant M as Mogul<br/>(suborchestrator)
    participant S as Subordinate<br/>(specialist/dynamic)
    participant GS as Governance Store<br/>(audit-logs/)
    participant H as Homeskillet<br/>(UX plane)
    participant U as Human

    T->>GS: Write mandate (pending)
    T->>M: Activate (nonblocking)

    M->>GS: Read mandate
    M->>GS: Transition mandate → running

    alt Direct execution
        M->>GS: Read governance surfaces
        M->>GS: Write artifacts
    else Specialist lane (blocking)
        M->>S: Delegate bounded task
        S->>GS: Read surfaces
        S->>GS: Write evidence
        S-->>M: Return findings
    else Dynamic lane (resumable)
        M->>S: Spawn bounded worker
        S->>GS: Read/Write iteratively
        S-->>M: Return synthesis
    end

    M->>GS: Write report + transcript
    M->>GS: Transition mandate → consumed
    M-->>H: Surface summary + escalations
    H-->>U: Present decision points
    U-->>H: Constitutional judgment
```

## 3. Governance Entity Relationship Diagram

```mermaid
erDiagram
    TIC {
        string tic_timestamp PK
        string tic_zone
        string cadence_position
        string scope
    }

    SIGNAL {
        string id PK
        string kind "BEACON|LESSON|OPPORTUNITY|TENSION"
        string band "PRIMITIVE|COGNITIVE|SOCIAL|PRESTIGE"
        int volume
        int volume_rate
        int max_volume
        string status "active|resolved|dismissed"
        string subsystem
    }

    WARRANT {
        string id PK
        string band
        string status
        string source_signal_id FK
    }

    CPR {
        string id PK
        string dedup_hash UK
        string status "extracted|tic_gated|enrichment_eligible|promotable|promoted|rejected|absorbed|skipped"
        string lesson
        string source
        int birth_tic
        string band
        string subsystem
    }

    ENRICHMENT {
        string evidence_type PK
        string value
        string gathered_by
        datetime gathered_at
    }

    MANDATE {
        string mandate_id PK
        string status "pending|running|consumed|failed"
        json actor
        json cycle_request
        json mode
        datetime created_at
        datetime completed_at
    }

    CONFORMATION {
        int tic PK
        datetime timestamp
        int active_signals
        int active_warrants
        int pending_cprs
        json rules_in_force
    }

    TIC ||--o{ SIGNAL : "drives decay/accrual"
    TIC ||--o{ CONFORMATION : "snapshots at boundary"
    SIGNAL ||--o| WARRANT : "mints when threshold crossed"
    CPR ||--o{ ENRICHMENT : "accumulates evidence"
    MANDATE ||--o{ CPR : "advances via cycles"
    MANDATE ||--o{ SIGNAL : "scans via cycles"
    CONFORMATION ||--o{ SIGNAL : "includes active"
    CONFORMATION ||--o{ WARRANT : "includes active"
    CONFORMATION ||--o{ CPR : "includes pending"
```

## 4. Component Architecture

```mermaid
graph TB
    subgraph PhysicsLayer["Physics Layer (deterministic enforcement)"]
        H1[cgg-bash-policy.py / PreToolUse]
        H2[cgg-completion-gate.py / Stop]
        H3[cgg-session-reinjection.sh / SessionStart or compact]
        H4[cgg-precompact-guard.sh / PreCompact]
        H5[cgg-subagent-provenance.py / SubagentStart or Stop]
        H6[cgg-config-audit.py / PostToolUse Write or Edit]
    end

    subgraph ScriptLayer["Script Layer (operational primitives)"]
        S1[signal-audit.py / --json metrics or view or audit]
        S2[runtime-sync.py / --json check or diff or sync]
        S3[burst-governor.py / tic emission plus economy]
        S4[governance-router.py / signal to action routing]
        S5[zone_root.py / path resolution primitive]
    end

    subgraph SkillLayer["Skill Layer (workflow payloads)"]
        SK1[/cadence / session epoch boundary]
        SK2[/review / constitutional bench]
        SK3[/siren / signal emission & triage]
        SK4[/telos-springboard / paper patching]
    end

    subgraph AgentLayer["Agent Layer (bounded judgment)"]
        MG[Mogul / governance suborchestrator]
        RA[Ripple Assessor / CPR evaluation]
        LA[Ladder Auditor / coherence audit]
        PC[Pattern Curator / MEMORY mining]
    end

    subgraph DataStores["Data Stores"]
        DS1[(audit-logs/signals/ JSONL append-only)]
        DS2[(audit-logs/cprs/ queue.jsonl)]
        DS3[(audit-logs/tics/ JSONL per day)]
        DS4[(audit-logs/mogul/ mandates and reports)]
        DS5[(audit-logs/conformations/ tic-N.json snapshots)]
        DS6[(.ticzone acoustic region config)]
    end

    subgraph UXLayer["UX + Synthesis"]
        HS[Homeskillet Opus 4.6]
    end

    subgraph ClockLayer["Clock Authority"]
        SW[Swann Governor Source-of-Clock sovereign]
    end

    %% Relationships
    HS -->|steers| MG
    MG -->|delegates| RA
    MG -->|delegates| LA
    MG -->|delegates| PC
    MG -->|surfaces| HS

    PhysicsLayer -.->|enforces rails| AgentLayer
    ScriptLayer -.->|invoked by| AgentLayer
    SkillLayer -.->|loaded by| AgentLayer
    SkillLayer -.->|loaded by| HS

    SW -->|emits tics| DS3
    SW -->|drives| DS1

    MG -->|reads/writes| DS1
    MG -->|reads/writes| DS2
    MG -->|reads| DS3
    MG -->|writes| DS4
    MG -->|reads| DS5

    S2 -->|syncs| ScriptLayer
    S1 -->|audits| DS1

    H3 -->|rehydrates from| DS4
    H4 -->|guards| DS4
    H5 -->|logs to| DS4
```
