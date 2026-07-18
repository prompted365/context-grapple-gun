//! CGG-owned adapter at the CovenantSlice → Temporal Splat boundary.
//!
//! CGG hydrates and progressively interprets the field. This crate binds that
//! field to one admitted covenant and produces the generic homeskillet protocol
//! request/proposal envelopes. The downstream temporal kernel never imports CGG.

pub mod adapter;
pub mod protocol;

pub use adapter::*;
pub use protocol::*;
