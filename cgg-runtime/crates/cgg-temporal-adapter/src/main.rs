use anyhow::{bail, Context, Result};
use cgg_temporal_adapter::{
    build_invocation_payload, normalize_proposal, prepare_request, CanonicalMountEnvelope,
    OutputAuthorityV1, PrepareRequestInput, SplatInterpretationRequestV1,
};
use serde::de::DeserializeOwned;
use std::fs;
use std::process::Command;

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
        [command, request, payload, mount] if command == "normalize-proposal" => {
            normalize(request, payload, mount)
        }
        [command, request, mount_bin] if command == "invoke" => invoke(request, mount_bin),
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

fn normalize(request_path: &str, payload_path: &str, mount_path: &str) -> Result<()> {
    let request: SplatInterpretationRequestV1 = read_json(request_path)?;
    let payload = fs::read_to_string(payload_path)
        .with_context(|| format!("failed to read {payload_path}"))?;
    let mount: CanonicalMountEnvelope = read_json(mount_path)?;
    let proposal = normalize_proposal(&request, &payload, mount)
        .context("failed to normalize bounded proposal")?;
    println!("{}", serde_json::to_string_pretty(&proposal)?);
    Ok(())
}

fn invoke(request_path: &str, mount_bin: &str) -> Result<()> {
    let request: SplatInterpretationRequestV1 = read_json(request_path)?;
    let payload = build_invocation_payload(&request)
        .context("failed to construct exact request-bound invocation payload")?;
    let authority = authority_name(request.authority_ceiling);
    let mut command = Command::new(mount_bin);
    command
        .arg("invoke")
        .arg("--office")
        .arg("ent_homeskillet")
        .arg("--lane")
        .arg("temporal-splat")
        .arg("--work-class")
        .arg("reasoning")
        .arg("--output-authority")
        .arg(authority)
        .arg("--tic")
        .arg(request.coordinate.global_tic.to_string())
        .arg("--payload")
        .arg(&payload);
    if let Ok(originator) = std::env::var("CANONICAL_MOUNT_ORIGINATOR") {
        command.arg("--originator").arg(originator);
    }
    let output = command
        .output()
        .with_context(|| format!("failed to invoke canonical-mount binary {mount_bin:?}"))?;
    if !output.status.success() {
        bail!(
            "canonical-mount exited {:?}: {}",
            output.status.code(),
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }
    let mount: CanonicalMountEnvelope = serde_json::from_slice(&output.stdout)
        .context("canonical-mount stdout is not a typed envelope")?;
    let proposal = normalize_proposal(&request, &payload, mount)
        .context("failed to verify live canonical-mount proposal")?;
    println!("{}", serde_json::to_string_pretty(&proposal)?);
    Ok(())
}

fn authority_name(authority: OutputAuthorityV1) -> &'static str {
    match authority {
        OutputAuthorityV1::Evidence => "evidence",
        OutputAuthorityV1::Advisory => "advisory",
        OutputAuthorityV1::Proposal => "proposal",
        OutputAuthorityV1::Proposing => "proposing",
        OutputAuthorityV1::Reasoning => "reasoning",
        OutputAuthorityV1::DelegatedExecution => "delegated_execution",
        OutputAuthorityV1::AdmittedMutation => "admitted_mutation",
    }
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

    cgg-temporal-adapter normalize-proposal <request.json> <payload.json> <canonical-mount.json>
        Recompute the exact payload/report/executable bindings and require the
        originator's own request binding before emitting SplatProposalEnvelopeV1.

    cgg-temporal-adapter invoke <request.json> <canonical-mount-bin>
        Construct the exact request-bound payload, invoke canonical-mount, verify
        both independent bindings, and emit the normalized proposal. The optional
        CANONICAL_MOUNT_ORIGINATOR environment variable selects an admitted originator.

The downstream homeskillet kernel consumes the generic protocol. It has no CGG
dependency and receives no untyped field hydration.
"#
    );
}
