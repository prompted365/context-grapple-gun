# CGG Terminology

CGG terms name governance distinctions. They are not required vocabulary for end users, but the distinctions are load-bearing.

| CGG term | Neutral systems alias | Meaning |
|---|---|---|
| CogPR | behavior pull request | A proposed durable lesson that has not yet become in-force truth. |
| born truth | local observation | A lesson captured near its source before broader authority is granted. |
| in-force truth | promoted rule | Guidance explicitly authorized for a named scope. |
| tic | ordered epoch event | ISO timestamp plus monotonic project counter used for total ordering. |
| zone | jurisdiction boundary | The project-local surface governed by `.ticzone` and `.ticignore`. |
| abstraction ladder | scope hierarchy | Site → Domain → Estate → Federation → Global. |
| hydration | bounded context rendering | Loading authorized guidance and current state into a working session. |
| hydration boundary | source/render separation | Constitutional source remains distinct from generated or rendered context. |
| signal | recurring condition | Friction or pressure tracked across work epochs. |
| warrant | escalation receipt | A signal that crossed its governed threshold and demands resolution. |
| handoff | continuity envelope | The bounded state and resume path carried into the next epoch. |
| conformation | state reconciliation | A receipt-bearing view of live governance state across relevant surfaces. |
| source runtime | canonical implementation | The repository or npm payload that defines intended behavior. |
| installed runtime | managed copy | The mode-specific bytes registered with Claude Code. |
| loaded runtime | behavioral truth | The plugin inventory Claude Code actually loaded for the current scope. |
| receipt | transition evidence | A durable record of what changed, under which authority, and with which version/evidence. |

## Three-state discipline

```text
born truth
  → proposed learning
  → human judgment
  → in-force truth at a named scope
```

No arrow is implied merely because a later surface is confident or because two stale surfaces agree.

## Command ownership

- `/cadence`: epoch boundary and handoff authority;
- `/review`: human constitutional judgment;
- `/siren`: signal operations;
- `cgg install`: zone/runtime bootstrap and plugin admission; the legacy `/init-governance` skill is currentness-held under issue #14.
