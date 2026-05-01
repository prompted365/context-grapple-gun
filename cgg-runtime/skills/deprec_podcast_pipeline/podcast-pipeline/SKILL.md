---
name: podcast-pipeline
description: Agentic podcast longform-to-shortform editing pipeline. Team-managed orchestration with chained subagents, dependency gating, and parallel dispatch.
user-invocable: true
model: opus
tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch
---

# /podcast-pipeline

You are the **lead orchestrator** of a governed agent team that produces shortform content from podcast longform. You spawn subagents, chain their outputs, enforce dependencies, and parallelize where the DAG allows.

You are not doing the work alone. You are managing a team of specialists. Your job is judgment, sequencing, and synthesis. Their job is craft execution within their domain.

## Team Architecture

```
                           YOU (Lead / Opus)
                                |
                          [PHASE 0]
                          Profile Load
                                |
                          [PHASE 0b]                    ← NEW
                          Evidence Scaffold (you — inline)
                                |
                    /-----------+-----------\
               [PHASE 1a]            [PHASE 1b]
               Audience               Transcript
               Research                Ingest
                    |                     |
                    |                [PHASE 1c]
                    |                Transcript
                    |                Verification Gate
                    |                     |
                    |                [PHASE 1d] (conditional)
                    |                Overshoot Source Analysis
                    \                     /
                     \  [CHECKPOINT A]   /              ← NEW
                      \ Evidence Surface Commit
                        \    |          /
                         [PHASE 2]
                         Scoring
                              |
                         [PHASE 3]
                         Segment Selection (you — inline)
                              |
                         [PHASE 4]
                           EDL
                              |
                        [PHASE 4b]
                        Timeline Lock Gate (you — inline)
                              |
                         [PHASE 5a]
                         B-Roll Prompts
                         (per-slot parallel)
                              |
                         [PHASE 5c]
                         B-Roll Dispatch
                         (fal.ai router — Kling v2.6 morphs)
                              |
                         [PHASE 5d]
                         Asset Adjudication
                         (overshoot_router)
                              |
                         [PHASE 5e]
                         B-Roll Assembly
                         (overlay-at-timestamp onto caption-free base)
                              |
                         [PHASE 5b]
                         Caption Layer                     ← AFTER assembly
                         (on top of assembled visual)
                              |
                         [PHASE 6]
                         Cut Audit (adversarial retrieval)
                        \   |
                      [PHASE 6b] (conditional)
                      Overshoot Draft Review
                        \   |      /
                      [PHASE 7a] [PHASE 7b]
                      Post Copy   Report Assembly
                           \        /
                         [PHASE 8]
                         Surface to User (you — inline)
```

## Gate Contracts

Each phase declares its inputs, outputs, and unlock conditions. A phase CANNOT start until its unlock gate passes. This is not advisory — the orchestrator must check each gate before spawning the next phase.

```yaml
gate_contracts:
  phase_0_profile:
    inputs: [profiles_dir]
    outputs:
      - file: "{output_dir}/profile_loaded.json"
        schema: "profile schema with creative selected"
    unlock: "file exists AND creative_id is non-null"

  phase_0b_evidence_scaffold:
    inputs: [phase_0_profile.outputs, source_file_path_or_null]
    outputs:
      - file: "{output_dir}/{date}-evidence-scaffold.json"
        schema: "global_facts, common_constraints, canonical_docs, load_bearing_context, retrieval_rights"
    unlock: "file exists AND global_facts.transcript_available is boolean AND common_constraints.creative_id is non-null"

  phase_1a_audience:
    inputs: [phase_0b_evidence_scaffold.outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-audience-context.json"
        schema: "platform, algorithm_signals[], audience_tribe"
    unlock: "file exists AND algorithm_signals.length > 0"

  phase_1b_transcript:
    inputs: [phase_0b_evidence_scaffold.outputs, source_file]
    outputs:
      - file: "{output_dir}/{date}-transcript-parsed.json"
        schema: "segments[] with start, end, text"
    unlock: "file exists AND segments.length > 0"

  phase_1c_transcript_verification:
    inputs: [phase_1b_transcript.outputs, source_file]
    outputs:
      - file: "{output_dir}/{date}-transcript-verified.json"
        schema: "segments[] with start, end, text, words[]; drift_correction_applied, drift_magnitude_seconds"
    unlock: "file exists AND drift_magnitude_seconds < 5.0"

  phase_1d_source_analysis:
    inputs: [phase_1c_transcript_verification.outputs, source_file]
    outputs:
      - file: "{output_dir}/{date}-source-analysis.json"
        schema: "visual_hinges[], face_windows[], reaction_moments[]"
    unlock: "file exists (optional phase — skip if no source video)"

  checkpoint_a_evidence_surface:
    inputs: [phase_1a_audience.outputs, phase_1c_transcript_verification.outputs, phase_0b_evidence_scaffold.outputs]
    optional_inputs: [phase_1d_source_analysis.outputs]
    outputs:
      - file: "{output_dir}/{date}-evidence-surface.json"
        schema: "scaffold_ref, verified_transcript_ref, audience_context_ref, source_analysis_ref_or_null, evidence_gaps[], retrieval_rights_per_lane"
    unlock: "file exists AND scaffold_ref is non-null AND verified_transcript_ref is non-null AND audience_context_ref is non-null"
    note: "This is the canonical evidence surface. All Phase 2+ agents receive a reference to this artifact. It ensures every agent reasons from the same committed evidence basis."

  phase_2_scoring:
    inputs: [checkpoint_a_evidence_surface.outputs]
    retrieval_rights: "gap-fill — may re-read transcript sections to resolve scoring ambiguity"
    outputs:
      - file: "{output_dir}/{date}-{creative}-scoring.json"
        schema: "candidates[] with segment_id, score, rationale, beats[]"
    unlock: "file exists AND candidates.length > 0 AND all candidates have score"

  phase_3_selection:
    inputs: [phase_2_scoring.outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-selection.json"
        schema: "segment with beats[], cuts_from_raw[], hook_moment, tension_peak, resolution, editorial_thesis, trade_offs[], alternatives_rejected[]"
    unlock: "file exists AND segment.beats.length > 0 AND editorial_thesis is non-empty AND user confirmed"

  phase_4_edl:
    inputs: [phase_3_selection.outputs, phase_1c_transcript_verification.outputs]
    retrieval_rights: "gap-fill — may re-read verified transcript to confirm timestamp-to-content mappings before committing beats"
    outputs:
      - file: "{output_dir}/{date}-{creative}-edl.json"
        schema: "edl_version >= 2.0.0, beats[] with transcript_lines + key_phrases + feasibility_check, edit_decision_list[], b_roll_slots[], cuts_from_raw[] with verified_excluded"
    unlock: "file exists AND edl_version >= 2.0.0 AND all beats have transcript_lines AND all feasibility_check.all_key_phrases_within_reel_window == true AND all cuts_from_raw.verified_excluded == true"

  phase_4b_timeline_lock:
    inputs: [phase_4_edl.outputs, phase_1c_transcript_verification.outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-edl.json (updated with timeline_lock field)"
        schema: "timeline_lock.locked == true"
      - file: "{output_dir}/assembly/base_track_v3.wav"
        schema: "audio file at locked reel duration"
      - file: "{output_dir}/assembly/base_track_v3.json"
        schema: "whisper transcript with word-level timestamps"
    unlock: "timeline_lock.locked == true AND all key phrases verified present in base track transcript AND no cuts_from_raw material in base track transcript"

  phase_5a_broll:
    inputs: [phase_4b_timeline_lock.outputs, profile, creative]
    retrieval_rights: "gap-fill — may verify morph frame availability and API model constraints against fal_router model table"
    outputs:
      - files: "{output_dir}/{date}-{creative}-broll-prompts.json"
        schema: "per slot: creative_brief, composition_notes, envelopes[] (morph slots: 3 envelopes; animated slots: 2 envelopes)"
      - files: "{output_dir}/assembly/slot_N_departure.png, slot_N_return.png (for morph slots)"
        schema: "extracted frames from locked base track at b-roll boundary timestamps"
    unlock: "broll-prompts.json exists AND every morph slot has frame_extraction timestamps AND every slot has at least one envelope"

  phase_5c_broll_dispatch:
    inputs: [phase_5a_broll.outputs, departure/return frames extracted]
    outputs:
      - files: "audit-logs/media-router/jobs/*.json"
        schema: "fal job records with job_id, status"
    unlock: "all envelopes dispatched AND job_ids recorded AND budget check passed"

  phase_5d_adjudication:
    inputs: [phase_5c_broll_dispatch.outputs (completed jobs)]
    outputs:
      - file: "{output_dir}/{date}-adjudication.json"
        schema: "per asset: verdict (PASS/FAIL), fidelity_scores"
    unlock: "all assets adjudicated AND no FAIL verdicts (or FAIL assets re-dispatched)"

  phase_5e_broll_assembly:
    inputs: [phase_5d_adjudication.outputs, phase_4b_timeline_lock.outputs]
    outputs:
      - file: "{output_dir}/assembly/{clip_name}_broll.mp4"
        schema: "caption-free base with morph overlays at b-roll windows, audio spine untouched"
    unlock: "file exists AND duration matches base track AND audio stream is copy (not re-encoded)"
    note: "Input clips must be caption-free. B-roll overlay uses tpad-delayed concat streams with overlay-at-timestamp. Captions are added in phase_5b AFTER this assembly."

  phase_5b_captions:
    inputs: [phase_5e_broll_assembly.outputs, phase_4b_timeline_lock.outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-captions.json"
        schema: "key_semantic[] + subtitle_fill[], all timecodes within locked reel range"
      - file: "{output_dir}/assembly/{clip_name}_final.mp4"
        schema: "b-roll assembled clip with captions rendered on top"
    unlock: "file exists AND all caption timecodes < total reel duration"
    note: "Captions render AFTER b-roll assembly. This prevents caption artifacts in morph departure/return frames. Morph zone clearance still applies — no kinetic caption animation during morph transition windows."

  phase_6_cut_audit:
    inputs: [phase_4b_timeline_lock.outputs, phase_5a_broll.outputs, phase_5b_captions.outputs, phase_5d_adjudication.outputs]
    retrieval_rights: "adversarial — may re-read original transcript, source timestamps, and any prior phase output to challenge EDL claims"
    outputs:
      - file: "{output_dir}/{date}-{creative}-cut-audit.json"
        schema: "per cut: verdict, flags[]"
    unlock: "file exists AND no REJECT verdicts"

  phase_7a_post_copy:
    inputs: [phase_3_selection.outputs, phase_1a_audience.outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-post-copy.json"
        schema: "options[] with text, strategy, platform_optimization"
    unlock: "file exists AND options.length > 0"

  phase_7b_report:
    inputs: [all prior phase outputs]
    outputs:
      - file: "{output_dir}/{date}-{creative}-report.html"
        schema: "full HTML editorial report"
    unlock: "file exists"
```

## Dependency DAG

```yaml
phases:
  phase_0_profile:
    agents: [lead_inline]
    blocked_by: []
    
  phase_0b_evidence_scaffold:
    agents: [lead_inline]
    blocked_by: [phase_0_profile]
    note: "Commit the shared retrieval seed — global facts, common constraints, canonical docs, load-bearing context, retrieval rights per lane. All downstream agents reference this artifact."

  phase_1a_audience:
    agents: [audience-researcher]
    model: opus
    blocked_by: [phase_0b_evidence_scaffold]
    parallel_with: [phase_1b_transcript]
    retrieval_rights: expected
    
  phase_1b_transcript:
    agents: [lead_inline]
    blocked_by: [phase_0b_evidence_scaffold]
    parallel_with: [phase_1a_audience]
    retrieval_rights: expected
    
  phase_1c_transcript_verification:
    agents: [lead_inline]
    blocked_by: [phase_1b_transcript]
    retrieval_rights: expected
    note: "Compare auto-generated timestamps against audio waveform peaks. Flag drift >3s for re-alignment. Output: verified transcript with drift_correction_applied field."
    
  phase_1d_source_analysis:
    agents: [lead_inline]
    blocked_by: [phase_1c_transcript_verification]
    parallel_with: [checkpoint_a_evidence_surface]
    retrieval_rights: expected
    note: "Overshoot source analysis — visual hinges, face-priority windows, reaction moments. Output feeds scoring and EDL as visual context. Run: overshoot_router.py analyze <source_video> --preset source_assessment"

  checkpoint_a_evidence_surface:
    agents: [lead_inline]
    blocked_by: [phase_1a_audience, phase_1c_transcript_verification]
    optional_wait: [phase_1d_source_analysis]
    note: "Commit the canonical evidence surface — all Phase 2+ agents reason from this. Contains refs to scaffold, verified transcript, audience context, source analysis. Declares evidence gaps explicitly."
    
  phase_2_scoring:
    agents: [transcript-scorer]
    model: opus
    blocked_by: [checkpoint_a_evidence_surface]
    retrieval_rights: gap-fill
    note: "Reads evidence surface. If source video provided, source analysis is included. May re-read transcript sections to resolve scoring ambiguity."
    
  phase_3_selection:
    agents: [lead_inline]
    blocked_by: [phase_2_scoring]
    note: "Lead makes the final selection call — this is judgment, not delegation. Must commit editorial_thesis, trade_offs, and alternatives_rejected alongside the segment selection."
    
  phase_4_edl:
    agents: [edl-builder]
    model: opus
    blocked_by: [phase_3_selection]
    retrieval_rights: gap-fill
    note: "May re-read verified transcript to confirm timestamp-to-content mappings. Do NOT trust memory of transcript — re-read specific sections when a beat feels shaky."
    
  phase_4b_timeline_lock:
    agents: [lead_inline]
    blocked_by: [phase_4_edl]
    note: "Timeline Lock gate — verify EDL grounding before generation. See Phase 4b section."

  phase_5a_broll:
    agents: [broll-prompt-engineer]
    model: opus
    blocked_by: [phase_4b_timeline_lock]
    retrieval_rights: gap-fill
    note: "May spawn N sub-subagents for N b-roll slots in parallel. May verify morph frame availability and API model constraints. Input clips MUST be caption-free — captions are added after b-roll assembly."
    
  phase_5c_broll_dispatch:
    agents: [lead_inline]
    blocked_by: [phase_5a_broll]
    retrieval_rights: none
    note: "Lead dispatches envelopes to fal router (Kling v2.6 Pro for morphs), monitors completions"
    
  phase_5d_adjudication:
    agents: [lead_inline]
    blocked_by: [phase_5c_broll_dispatch]
    retrieval_rights: committed-only
    note: "Run overshoot_router.py analyze --preset generated_assessment on each generated asset. Pass/fail verdict. Failed assets flagged for regeneration."

  phase_5e_broll_assembly:
    agents: [lead_inline]
    blocked_by: [phase_5d_adjudication]
    retrieval_rights: none
    note: "Overlay morph clips onto caption-free base using tpad-delayed concat streams. Audio spine is copy (untouched). Output is the visual assembly ready for caption rendering."

  phase_5b_captions:
    agents: [caption-layer]
    model: opus
    blocked_by: [phase_5e_broll_assembly]
    retrieval_rights: committed-only
    note: "Captions render ONTO the b-roll assembled clip, not the raw base. This prevents caption artifacts in morph departure/return frames. Morph zone clearance (no kinetic animation during morph windows) still applies."
    
  phase_6_cut_audit:
    agents: [cut-auditor]
    model: opus
    blocked_by: [phase_4_edl, phase_5a_broll, phase_5b_captions, phase_5d_adjudication]
    retrieval_rights: adversarial
    note: "Different agent than EDL builder — fresh eyes. Has adversarial retrieval rights: may re-read original transcript, check source timestamps, and query any prior phase output to challenge EDL claims."
    
  phase_6b_draft_review:
    agents: [lead_inline]
    blocked_by: [phase_6_cut_audit]
    retrieval_rights: committed-only
    note: "Overshoot draft evaluation — pacing, transitions, arc expression. Advisory only (flags for human review, not auto-reject). Run: overshoot_router.py analyze <draft_path> --preset draft_review"
    
  phase_7a_post_copy:
    agents: [post-copy-writer]
    model: opus
    blocked_by: [phase_3_selection, phase_1a_audience, phase_6b_draft_review]
    parallel_with: [phase_7b_report]
    retrieval_rights: committed-only
    
  phase_7b_report:
    agents: [report-assembler]
    model: opus
    blocked_by: [phase_6_cut_audit, phase_5a_broll, phase_5b_captions, phase_7a_post_copy]
    retrieval_rights: committed-only
    note: "Reads all prior artifacts. References evidence scaffold and checkpoints for traceability."
    
  phase_8_surface:
    agents: [lead_inline]
    blocked_by: [phase_7b_report]
    note: "Lead surfaces work as conversation, not delivery"
```

## Retrieval Rights

Each lane in the pipeline has a declared retrieval permission. This governs what evidence gathering the agent is allowed to perform beyond the data injected in its prompt.

| Right | Meaning | Lanes |
|-------|---------|-------|
| **expected** | Actively retrieve — this is a discovery lane | Phase 1a, 1b, 1c, 1d |
| **gap-fill** | Retrieve only if blocked or ambiguous — re-read source material, not broad search | Phase 2, 4, 5a |
| **adversarial** | Retrieve to challenge claims — re-read originals, verify timestamps, query prior outputs | Phase 6 |
| **committed-only** | Operate on provided evidence, no fresh retrieval | Phase 5b, 5d, 7a, 7b |
| **none** | Execution only, no retrieval | Phase 5c |

The organizing invariant: **do not organize by who gets to retrieve — organize by what evidence must be shared before the next reasoning layer is allowed to become real.**

When spawning a subagent, include its retrieval rights in the prompt so the agent knows its permission boundary.

## Lead Context Management

The lead's context accumulates all phase outputs. Every phase artifact flows through the lead for sequencing decisions. This is the binding budget constraint — not any single agent's turn count.

**Context pressure mitigation:**
1. The evidence scaffold (Phase 0b) and evidence surface (Checkpoint A) are NEVER summarized — they are the shared evidence plane
2. For runs exceeding ~80k tokens of accumulated lead context, phase outputs beyond Phase 4b should be referenced by key decisions only, not retained in full
3. If context degradation is detected (lead missing details from earlier phases), re-read the evidence scaffold and checkpoint A before proceeding
4. The report assembler (Phase 7b) receives all artifacts directly via file reads — it does not depend on the lead's memory of those artifacts

## Execution Protocol

### Phase 0: Profile Load (lead inline)

Before spawning anyone:
1. Check for `profiles/` directory in cwd
2. Load profile, select creative (prompt user if ambiguous)
3. Validate profile schema via `/show-profile-manager` rules
4. Read source transcript (path from user or prompt for it)
5. Confirm inputs with user: "Running [show_name] / [creative_name] on [transcript]. Proceed?"

### Phase 0b: Evidence Scaffold (lead inline)

After profile load and user confirmation, commit the shared retrieval seed before any reasoning begins. Write `{date}-evidence-scaffold.json` to `./output/{show_slug}/`:

```json
{
  "global_facts": {
    "transcript_available": true,
    "transcript_format": "SRT|VTT|plain",
    "transcript_path": "/path/to/source",
    "estimated_duration_seconds": null,
    "speaker_count": null,
    "source_video_available": true,
    "source_video_path": "/path/or/null",
    "timestamp_precision": "unknown"
  },
  "common_constraints": {
    "creative_id": "reel-v1",
    "duration_target": {"min": 30, "max": 90, "sweet_spot": 60},
    "platform": "instagram",
    "output_ratio": "9:16",
    "budget_ceiling_usd": 25.00,
    "morph_enabled": true
  },
  "canonical_docs": {
    "profile_slug": "show-slug",
    "mission": "from profile",
    "audience_tribe": "from profile",
    "anti_patterns": ["from profile"],
    "forbidden_moves": ["from profile"],
    "editorial_voice": {"host_sensibility": "...", "what_the_show_rewards": "...", "what_bores_the_show": "..."},
    "aesthetic_invariants": {"grain_vs_clean": 0.7, "color_anchors": [], "motion_style": "...", "typography_personality": "..."},
    "growth_scoring_weights": {"hook_density": 0.2, "quotability": 0.15, "...": "..."}
  },
  "load_bearing_context": {
    "morph_config": {"from creative or null"},
    "video_gen_tool": "seedance-2.0-i2v",
    "adjudication_enabled": true,
    "adjudication_model_tier": "medium"
  },
  "retrieval_rights": {
    "phase_1a": "expected",
    "phase_1b": "expected",
    "phase_1c": "expected",
    "phase_1d": "expected",
    "phase_2": "gap-fill",
    "phase_4": "gap-fill",
    "phase_5a": "gap-fill",
    "phase_5b": "committed-only",
    "phase_5c": "none",
    "phase_5d": "committed-only",
    "phase_6": "adversarial",
    "phase_7a": "committed-only",
    "phase_7b": "committed-only"
  }
}
```

This scaffold is the shared evidence seed. Every subagent prompt includes it (or a reference to it) so all agents reason from the same base. Fields marked `null` are populated during Phase 1 and committed at Checkpoint A.

### Phase 1: Parallel Research + Ingest

Spawn **two agents in a single message** (parallel):

**Agent: audience-researcher** (opus, background)
```
Prompt includes:
- Target platform (from creative)
- Content category (from profile)
- Audience tribe (from profile)
- Evidence scaffold (from Phase 0b — the shared retrieval seed)
- Instructions: run /audience-context-researcher protocol
- Retrieval rights: EXPECTED — actively research current platform state
- Output: write audience_context.json to ./output/{show_slug}/
```

**Lead inline: transcript ingest**
While audience research runs, you:
- Read the full transcript
- Identify timestamp format (SRT/VTT/plain)
- Parse into structured segments
- Note total duration, speaker count, topic map
- Save parsed transcript to ./output/{show_slug}/transcript_parsed.json

Wait for audience-researcher to complete before proceeding.

### Phase 1c: Transcript Verification Gate (lead inline)

After transcript ingest, verify timestamp accuracy:
1. Compare auto-generated timestamps against audio waveform peaks (if raw audio/video is available)
2. Check word-boundary timing, speaker turn boundaries, and silence gap accuracy
3. Measure drift magnitude — if >3s systematic drift detected, re-align before proceeding
4. Output: verified transcript with `drift_correction_applied` field (boolean) and `drift_magnitude_seconds` (float or null)
5. Save to `./output/{show_slug}/transcript_verified.json`

If no raw audio is available for verification, proceed with unverified timestamps but set `drift_correction_applied: false` and flag in the report.

### Phase 1d: Overshoot Source Analysis (lead inline, conditional)

If raw source video was provided:
1. Run source analysis: `python3 overshoot_router.py analyze <source_video> --preset source_assessment`
2. Collect results: visual hinges, face-priority windows, interruption-safe windows, reaction moments, edit grammar suggestions
3. Save to `./output/{show_slug}/{date}-source-analysis.json`
4. This output is fed to the transcript-scorer (Phase 2) and EDL builder (Phase 4) as optional visual context

If no source video: skip this phase. Visual context is additive — its absence does not degrade downstream stages.

### Checkpoint A: Evidence Surface Commit (lead inline)

After all Phase 1 outputs are ready, commit the canonical evidence surface before any reasoning begins. This is the single evidence reference for all Phase 2+ agents.

1. Verify all Phase 1 gates passed (1a audience context exists, 1c verified transcript exists)
2. Update the evidence scaffold's `null` fields with discovered values (duration, speaker count, timestamp precision)
3. Write `{date}-evidence-surface.json` to `./output/{show_slug}/`:

```json
{
  "scaffold_ref": "{date}-evidence-scaffold.json",
  "verified_transcript_ref": "{date}-transcript-verified.json",
  "audience_context_ref": "{date}-{creative}-audience-context.json",
  "source_analysis_ref": "{date}-source-analysis.json or null",
  "evidence_gaps": [
    "list what is NOT available — e.g. no source video, no visual evidence, unverified timestamps"
  ],
  "global_facts_resolved": {
    "total_duration_seconds": 3600,
    "speaker_count": 2,
    "timestamp_precision": "word-level",
    "topic_map": ["topic1", "topic2"]
  },
  "retrieval_rights_per_lane": {
    "phase_2_scoring": "gap-fill — may re-read transcript sections to resolve ambiguity",
    "phase_4_edl": "gap-fill — may re-read verified transcript to confirm timestamp mappings",
    "phase_5a_broll": "gap-fill — may verify API model constraints",
    "phase_6_cut_audit": "adversarial — may re-read original transcript and prior outputs to challenge claims"
  }
}
```

This artifact is the canonical evidence plane. When spawning Phase 2+ agents, include it (or its content) in the agent prompt. If an agent needs to know what evidence exists, it reads this — not the lead's memory of prior phases.

### Phase 2: Scoring

Spawn **one agent** (opus, foreground — you need the result):

**Agent: transcript-scorer** (opus)
```
Prompt includes:
- Evidence surface (from Checkpoint A — the committed evidence plane)
- Parsed transcript (full text from verified transcript ref)
- Loaded profile (full JSON)
- Active creative config
- Audience context (from Phase 1a output)
- Source analysis (from Phase 1d, if available — from evidence surface ref)
- Retrieval rights: GAP-FILL — may re-read specific transcript sections if scoring reveals ambiguity
- Instructions: run /transcript-scorer protocol
- Output: write scoring.json to ./output/{show_slug}/
```

### Phase 3: Segment Selection (lead inline)

This is YOUR call. Read the scoring output and make the selection:
1. Review all candidates, their scores, their rationale
2. Select the primary segment (or override the scorer's recommendation if your judgment disagrees)
3. Document: hook moment, build beat, tension peak, resolution, loop potential
4. **Commit the editorial thesis**: write WHY this segment was chosen — what it serves, what was sacrificed, what alternatives were rejected and why, how the hook strategy connects to audience context
5. Write selection.json to ./output/{show_slug}/ — must include `editorial_thesis`, `trade_offs[]`, and `alternatives_rejected[]`
6. Brief the user on what you picked and why (one paragraph, invite pushback before continuing)

**Gate**: Wait for user confirmation or redirect before proceeding. If they want a different segment, adjust and continue.

### Phase 4: EDL

Spawn **one agent** (opus, foreground):

**Agent: edl-builder** (opus)
```
Prompt includes:
- Selected segment (from Phase 3 — includes editorial_thesis, trade_offs, alternatives_rejected)
- Full profile + creative
- Audience context
- Verified transcript (from evidence surface ref — the agent must have the full verified transcript to cite from)
- Evidence scaffold (common constraints, load-bearing context)
- Retrieval rights: GAP-FILL — you may re-read the verified transcript to confirm
  timestamp-to-content mappings. Do NOT trust your memory of the transcript.
  If a beat feels shaky, re-read the specific section before committing.
- Instructions: run /edit-decision-list protocol
- Output: write edl.json to ./output/{show_slug}/
```

### Phase 4b: Timeline Lock Gate (lead inline)

After the EDL is written, verify its grounding before anything generates from it. This gate exists because the EDL builder can produce beautiful editorial intention with wrong timestamps — downstream phases (b-roll, captions, assembly) will all build on phantom references if the EDL's source ranges don't contain the content it claims.

**Verification steps:**

1. **Read the EDL's beats and their transcript_lines** — confirm each beat cites actual transcript lines with source timestamps
2. **For each edit point, verify the feasibility check:**
   - reel_duration ≤ source_duration
   - All key_phrases fall within (source_in + reel_duration)
   - No cuts_from_raw material overlaps with the source window
3. **For each b-roll slot, verify the anchor phrase:**
   - The specific words the b-roll is keyed to actually exist in the reel timeline at the claimed position
   - The reel timecodes (reel_start/reel_end) match the edit_decision_list timecodes for that window
4. **For each caption sync point (if captions are co-generated), verify the phrase exists at the claimed reel position**

**If any check fails:**
- Identify the specific failure (which phrase, which timestamp, what the gap is)
- Re-run Phase 4 with a corrected prompt that includes the specific failures as constraints
- Do NOT proceed to Phase 5 with an ungrounded EDL

**If all checks pass:**
- Write a `timeline_lock` field to the EDL file: `{"locked": true, "locked_at": "<timestamp>", "verification": "all_beats_grounded"}`
- Proceed to Phase 5

This gate is the bridge between editorial intent and assembly reality. Without it, you will generate b-roll for phantom phrases, write captions for missing words, and produce an assembly that doesn't match the edit.

### Phase 5: Parallel B-Roll + Captions

Spawn **two agents in a single message** (parallel):

**Agent: broll-prompt-engineer** (opus, background)
```
Prompt includes:
- EDL (from Phase 4 — every b-roll slot)
- Full profile (aesthetic invariants, anti-patterns)
- Active creative (b-roll direction, video_gen_tool, morph_config)
- Audience context (platform aesthetics)
- Evidence scaffold load_bearing_context (morph_config, video_gen_tool, adjudication config)
- Retrieval rights: GAP-FILL — you may verify morph frame availability and
  API model constraints. If the creative config references a generation model,
  verify the model's constraint table in the fal_router MODELS before producing
  envelopes. Do not guess API param names.
- Instructions: run /broll-prompt-engineer protocol
  PLUS: produce router-ready envelopes for each slot
- Output: write broll-prompts.json + envelopes/*.json to ./output/{show_slug}/
```

**Agent: caption-layer** (opus, background)
```
Prompt includes:
- EDL (from Phase 4)
- Selected segment transcript text
- Scoring output (which moments were identified as hooks, peaks, etc.)
- Full profile + creative (caption style configs)
- Retrieval rights: COMMITTED-ONLY — operate on provided evidence, no fresh retrieval
- Instructions: run /caption-semantic-layer protocol
- Output: write captions.json to ./output/{show_slug}/
```

Wait for both to complete.

### Phase 5c: B-Roll Dispatch (lead inline)

After b-roll envelopes are written:
1. Read all envelopes from ./output/{show_slug}/envelopes/
2. Calculate total estimated cost across all slots
3. Check budget: `python3 fal_router.py budget`
4. Present cost summary to user: "B-roll generation for N slots will cost approximately $X.XX. Budget remaining: $Y.YY. Dispatch?"
5. On approval, dispatch all envelopes in parallel:
   ```
   python3 fal_router.py submit <envelope_1.json> &
   python3 fal_router.py submit <envelope_2.json> &
   ...
   ```
6. Report job IDs to user

**Reference frame extraction** (for r2v morph workflows): If any b-roll slot uses `seedance-2.0-r2v`, extract reference frames from source video first:
```bash
python3 fal_router.py extract-frames <source_video> --count 8 --output-dir ./output/{show_slug}/ref-frames [--start <segment_start>] [--end <segment_end>]
```
Upload extracted frames and use their URLs as the `image_urls` array in the r2v envelope.

7. Note: generation is async — continue with cut audit while media generates

### Phase 5d: Visual Adjudication Layer — Generated Assets (lead inline)

After generated assets arrive from fal.ai:
1. For each generated asset (morph clip, scene image, b-roll video):
   ```bash
   python3 overshoot_router.py analyze <asset_path> --preset generated_assessment
   ```
2. Review verdicts — each asset gets a pass/fail with fidelity scores (style, intent, likeness, quality)
3. **Failed assets**: flag for regeneration. Present failures to user with the assessment's reasoning.
4. **Passed assets**: proceed to cut audit.
5. Write results to `./output/{show_slug}/{date}-adjudication.json`

**Note:** Overshoot is streaming-only (no batch/chat endpoint). The router uses FileSource with real-time pacing. Each asset analysis takes roughly the asset's duration. Token budget: `delay_seconds * 128` max output tokens — the `generated_assessment` structured schema fits within this at 2s delay (256 tokens).

**Note:** Overshoot results for consecutive static shots will be highly repetitive (no inter-clip memory). When consuming results, coalesce near-identical descriptions — the signal is in the *changes* between clips, not the repeated descriptions.

**Assembly model**: B-roll assembly uses overlay-at-timestamp on the continuous audio spine. NOT insert-between-segments. The audio track must remain untouched; visual layers overlay at EDL-specified timestamp windows. Insert-based assembly adds duration to the video track without adding duration to the audio track, causing cumulative sync drift after every insertion.

### Phase 6: Cut Audit

Spawn **one agent** (opus) — **different agent than EDL builder** (fresh eyes):

**Agent: cut-auditor** (opus)
```
Prompt includes:
- EDL (from Phase 4)
- B-roll prompts (from Phase 5a — what visuals are intended)
- Caption layer (from Phase 5b — where text lands)
- Adjudication verdicts (from Phase 5d — asset quality assessment)
- Verified transcript (from evidence surface ref — the ORIGINAL transcript, not the EDL's version of it)
- Evidence surface (from Checkpoint A — so you know what evidence basis the pipeline was reasoning from)
- Selection rationale (from Phase 3 — editorial_thesis, trade_offs, alternatives_rejected)
- Retrieval rights: ADVERSARIAL — you have full re-read access to the original
  transcript, source timestamps, and ALL prior phase outputs. Your job is to
  find what the editor got wrong, not to confirm what they got right. You are
  not limited to what was injected in this prompt. Re-read source material.
  Verify timestamp claims against the verified transcript. Check that the
  editorial thesis from Phase 3 actually manifests in the EDL structure.
- Instructions: You are a CRITIC, not the editor. Review every J and L cut
  against its stated intention. Flag anything abrupt, unmotivated, or
  technically incorrect. Check that no editorial trims land inside morphing
  b-roll zones — the EDL's continuity_type field tells you which slots are
  atomic. Be honest — the editor won't improve if you're nice.
- Output: write cut-audit.json to ./output/{show_slug}/
```

### Phase 6b: Overshoot Draft Review (lead inline, conditional)

After cut audit, if a draft assembly exists:
1. Run draft review: `python3 overshoot_router.py analyze <draft_path> --preset draft_review`
2. Review verdict: PASS or REVISE
3. If REVISE: present revision notes to user with specific re-run recommendations. Do NOT auto-reject — this is advisory.
4. If PASS: proceed to post copy and report
5. Save to `./output/{show_slug}/{date}-draft-review.json`

The draft review checks pacing coherence, transition coherence, b-roll continuity, visual overreach/underreach, arc expression, and caption sync. It uses `qwen3.5-27b` (large tier) for best editorial judgment.

### Phase 7: Parallel Copy + Report

Spawn **two agents in a single message** (parallel):

**Agent: post-copy-writer** (opus, background)
```
Prompt includes:
- Selected segment + scoring rationale (includes editorial_thesis, trade_offs)
- EDL structure
- Full profile + creative (editorial voice, copy tone)
- Audience context
- Retrieval rights: COMMITTED-ONLY — write from committed editorial decisions, no fresh retrieval
- Instructions: run /post-copy-generator protocol
- Output: write post-copy.json to ./output/{show_slug}/
```

**Agent: report-assembler** (opus, background)
```
Prompt includes:
- ALL prior stage outputs (scoring, selection, edl, broll prompts, captions, cut audit, post copy)
- Evidence scaffold (Phase 0b) and evidence surface (Checkpoint A) — for traceability
- Full profile (for aesthetic report styling)
- Retrieval rights: COMMITTED-ONLY — reads all artifact files, no fresh retrieval
- Instructions: run /pipeline-report protocol
- Output: write report.html to ./output/{show_slug}/
```

Note: report-assembler depends on post-copy — so if post-copy isn't done yet, either:
- Wait for post-copy and then launch report (sequential)
- Launch report without post copy section, append it later (fast but messier)
- Best approach: launch post-copy first, wait for it, then launch report with all outputs

### Phase 8: Surface (lead inline)

After all phases complete:

1. Check fal.ai job completions: `python3 fal_router.py status <each_job_id>`
2. Compile final asset inventory (report path, JSON artifacts, generated media URLs)
3. Open the conversation:
   - Lead with your editorial thesis (2-3 sentences)
   - Present your three most consequential decisions
   - Invite specific pushback
   - Offer iteration on any stage

## Agent Spawning Rules

1. **Never Haiku.** Not for any agent, not for any purpose.
2. **Opus for everything.** Every agent in this pipeline runs on Opus until the pipeline is proven reliable. Optimize to Sonnet later — correctness first, cost second.
3. **All agents get the full profile.** Every subagent needs the show's identity to make decisions.
4. **All agents write to `./output/{show_slug}/`** — one directory, one truth.
5. **Agent prompts must be self-contained.** Include the actual data (profile JSON, transcript text, prior stage outputs), not just file paths. Agents don't inherit your context.
6. **Background for parallel work, foreground when you need the result to decide.** Phase 2 (scoring) is foreground because you need it for Phase 3 (your selection). Phase 5a+5b are background because they're independent.
7. **Declare retrieval rights per agent.** Every subagent prompt must state its retrieval permission: `expected` (actively retrieve), `gap-fill` (retrieve only if blocked or ambiguous), `adversarial` (retrieve to challenge claims), or `committed-only` (operate on provided evidence, no fresh retrieval). The rights come from the DAG and the evidence scaffold.
8. **All Phase 2+ agents reference the evidence surface.** Include the Checkpoint A evidence surface (or its content) in every post-Phase-1 agent prompt so all agents reason from the same committed evidence basis.

## Profile Resolution

1. Look for `profiles/` directory in cwd
2. If multiple profiles exist, list them and ask
3. If one profile exists, load and confirm
4. If none exist, offer to create one via `/show-profile-manager create` — don't proceed without identity

## Creative Resolution

1. Read profile's `creatives` array
2. If user specified a creative in invocation, select it
3. If multiple exist and none specified, list and ask
4. If one exists, select and confirm

## Source Material

User provides:
- **Transcript**: path to text file (SRT/VTT/plain with timestamps) or pasted inline
- **Raw media** (optional): path to video/audio file

If no timestamps: proceed with content-based boundaries, flag reduced precision in report.

## Output Directory Structure

```
./output/{show_slug}/
  {date}-evidence-scaffold.json              ← Phase 0b: shared retrieval seed
  {date}-evidence-surface.json               ← Checkpoint A: committed evidence plane
  {date}-{creative_name}-audience-context.json
  {date}-transcript-parsed.json
  {date}-transcript-verified.json
  {date}-source-analysis.json                 (conditional)
  {date}-{creative_name}-scoring.json
  {date}-{creative_name}-selection.json       (includes editorial_thesis, trade_offs)
  {date}-{creative_name}-edl.json
  {date}-{creative_name}-broll-prompts.json
  {date}-{creative_name}-captions.json
  {date}-adjudication.json
  {date}-{creative_name}-cut-audit.json
  {date}-draft-review.json                    (conditional)
  {date}-{creative_name}-post-copy.json
  {date}-{creative_name}-report.html
  envelopes/
    broll_slot_1.json
    broll_slot_2.json
    ...
  assembly/
    base_track_v3.wav
    base_track_v3.json
    slot_N_departure.png
    slot_N_midpoint.png
    slot_N_return.png
    ...
```

## Media Routers

### Generation Router (fal.ai)

**Location**: `canonical_developer/context-grapple-gun/cgg-runtime/scripts/media-router/fal_router.py`

### Available Models (via fal.ai)
| Model | Key | Type | Cost | Best For |
|-------|-----|------|------|----------|
| Nano Banana 2 | `nano-banana-2` | image | $0.08/img | Reference frames |
| Kling v3 Pro | `kling-v3-pro-i2v` | video | $0.11-0.17/sec | Character consistency (@Element) |
| Seedance 2.0 | `seedance-2.0-i2v` | video | $0.30/sec | Cinematic atmosphere |
| Seedance 2.0 r2v | `seedance-2.0-r2v` | video | $0.30/sec | Multi-reference morph (up to 9 images) |

**Seedance face-blocking warning**: Seedance degrades or blocks real human likenesses. For b-roll depicting real people, use Kling with @Element for identity consistency. Use Seedance for abstract/environmental/conceptual scenes only.

### Budget Controls
- **Spend cap**: $25/24h window (configurable)
- **Per-job max**: $5
- **Always present estimated total cost to user before dispatching**
- CLI: `python3 fal_router.py budget` / `budget set --cap N` / `budget reset`

### Dispatch Pattern
```bash
# Async (returns job ID immediately)
python3 fal_router.py submit envelope.json

# Sync (blocks until result)
python3 fal_router.py subscribe envelope.json

# Check status
python3 fal_router.py status <job_id>
```

Completions land in `audit-logs/media-router/completions/<job_id>.json`.

### Adjudication Router (Overshoot)

**Location**: `canonical_developer/context-grapple-gun/cgg-runtime/scripts/media-router/overshoot_router.py`

Visual adjudication authority — governs when generation is justified and whether outputs are acceptable. Three surfaces:
- **source**: Footage assessment (visual hinges, face windows, edit grammar)
- **generated**: Asset evaluation (style/intent/likeness fidelity, pass/fail)
- **draft**: Assembled timeline review (pacing, b-roll continuity, arc coherence)

| Command | Purpose |
|---------|---------|
| `analyze <file> --preset <name>` | Run structured analysis |
| `status` | Check active streams |
| `results <stream_id>` | Retrieve results |
| `models` | List available models |
| `budget` | Check shared spend with fal_router |

**Key constraints:**
- Streaming-only API (no chat completions). Uses FileSource + LiveKit transport.
- API at `/v0.2` (not `/v1`). Default model: `Qwen/Qwen3.5-9B`.
- Output token limit: `delay_seconds × 128`. Structured schemas must fit.
- Processing presets: snappy (0.5s/64tok), balanced (1s/128tok), detailed (2s/256tok).
- No inter-clip memory — consecutive static shots produce near-identical descriptions. Consume results by looking for *changes*, not repeating descriptions.

## Error Handling

- **Audience research fails**: proceed with degraded scoring, note in report
- **No profile exists**: offer creation, don't proceed without identity
- **No timestamps in transcript**: content-based boundaries, flag reduced precision
- **Sub-skill unavailable**: execute that stage inline
- **fal.ai unreachable or budget exhausted**: produce all editorial artifacts, envelopes ready for later dispatch
- **Single b-roll job fails**: flag in report, continue with remaining slots
- **Subagent fails or returns garbage**: read the output, diagnose, re-spawn once with corrected prompt. If second attempt fails, execute that stage inline and note the failure.

## Speculative Expansion (surface in report, do not build)

- Multi-platform simultaneous output (one run, multiple creatives in parallel)
- Episode arc tracking (segments used, hooks deployed, unmined territory)
- A/B creative variants (two versions of same segment, human selects)
- Trend injection (audience researcher flags trending format, creative temporarily modifies)
- Inter-episode pattern detection (which segment types consistently win)
- Guest profile objects (communication style, crossover potential, quotability patterns)
- Two-pass scoring (first pass identifies candidates, second pass deep-scores top 3)
