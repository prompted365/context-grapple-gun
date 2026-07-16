# cgg-temporal-adapter

CGG-owned, pure-Rust cable between the covenant-splat skill and the generic temporal runtime protocol.

```text
hydrated CovenantSlice + admitted covenant
    → prepare-request
    → SplatInterpretationRequestV1
    → canonical-mount invoke
    → normalize-proposal
    → SplatProposalEnvelopeV1
    → homeskillet-csl temporal intake
```

The adapter binds covenant identity, admission receipt, tic and causal frontier, source hashes, five independent status axes, authority ceiling, and center exclusion. It refuses stale slices, malformed hashes, non-actual ingress, authority widening, missing six-facet material, provider failure, and every terminalization claim.

It does not infer missing covenant content, fill missing facets, choose a route, execute Harpoon, write canonical state, or terminalize governance.

```bash
cargo run --manifest-path Cargo.toml -- prepare-request binding.json
cargo run --manifest-path Cargo.toml -- normalize-proposal request.json canonical-mount.json
cargo test --manifest-path Cargo.toml
```

Wire protocol pin:

```text
temporal-splat-protocol-v1 schema sha256
817abcdd53e572ce97f77c27149cf42ec26df98915bdb70cd2ebc879bdde951b
```
