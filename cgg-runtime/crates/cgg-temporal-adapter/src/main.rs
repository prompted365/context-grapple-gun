use anyhow::{bail, Context, Result};
use cgg_temporal_adapter::{
    normalize_proposal, prepare_request, CanonicalMountEnvelope, PrepareRequestInput,
    SplatInterpretationRequestV1,
};
use serde::de::DeserializeOwned;
use std::fs;

fn main() {
    if let Err(error) = run() {
        eprintln!("cgg-temporal-adapter: {error:#}");
        std::process::exit(2);
    }
}

fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [command, input] if command == "prepare-request" => prepare(input),
        [command, request, mount] if command == "normalize-proposal" => normalize(request, mount),
        [command] if matches!(command.as_str(), "help" | "--help" | "-h") => {
            print_help();
            Ok(())
        }
        [] => {
            print_help();
            Ok(())
        }
        _ => bail!("unknown or incomplete command; run `cgg-temporal-adapter --help`"),
    }
}

fn prepare(path: &str) -> Result<()> {
    let input: PrepareRequestInput = read_json(path)?;
    let request = prepare_request(input).context("failed to bind hydrated field to request")?;
    println!("{}", serde_json::to_string_pretty(&request)?);
    Ok(())
}

fn normalize(request_path: &str, mount_path: &str) -> Result<()> {
    let request: SplatInterpretationRequestV1 = read_json(request_path)?;
    let mount: CanonicalMountEnvelope = read_json(mount_path)?;
    let proposal =
        normalize_proposal(&request, mount).context("failed to normalize bounded proposal")?;
    println!("{}", serde_json::to_string_pretty(&proposal)?);
    Ok(())
}

fn read_json<T: DeserializeOwned>(path: &str) -> Result<T> {
    let text = fs::read_to_string(path).with_context(|| format!("failed to read {path}"))?;
    serde_json::from_str(&text).with_context(|| format!("{path} is not valid typed JSON"))
}

fn print_help() {
    println!(
        r#"cgg-temporal-adapter — CGG-owned temporal interpreter cable

USAGE:
    cgg-temporal-adapter prepare-request <binding.json>
        Bind one hydrated CovenantSlice to an admitted covenant, exact tic,
        source hashes, status axes, authority ceiling, and center-exclusion law.
        Emits SplatInterpretationRequestV1.

    cgg-temporal-adapter normalize-proposal <request.json> <canonical-mount.json>
        Validate the canonical-mount civic/provider envelope and normalize its
        InterpretationResultV1 into SplatProposalEnvelopeV1, cryptographically
        bound to the exact request. Emits artifacts only; never terminalizes.

The downstream homeskillet kernel consumes the generic protocol. It has no CGG
dependency and receives no untyped field hydration.
"#
    );
}
