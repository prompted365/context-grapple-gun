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

The adapter binds covenant identity, admission receipt, tic and causal frontier, source hashes, five independent status axes, authority ceiling, center exclusion, exact invocation payload bytes, exact result bytes, and the canonical-mount executable commit. It refuses stale slices, malformed hashes, non-actual ingress, authority widening, missing six-facet material, provider failure, and every terminalization claim.

It does not infer missing covenant content, fill missing facets, choose a route, execute Harpoon, write canonical state, or terminalize governance.

```bash
cargo run --manifest-path Cargo.toml -- prepare-request binding.json
cargo run --manifest-path Cargo.toml -- normalize-proposal request.json payload.json canonical-mount.json
cargo run --manifest-path Cargo.toml -- invoke request.json /path/to/canonical-mount
cargo test --manifest-path Cargo.toml
```

Wire protocol pin:

```text
temporal-splat-protocol-v1 schema sha256
42e4f35f9b7a8c0f6ec82529ea71948c1ab33f51174adb93fa07b21316fa2e75
```
