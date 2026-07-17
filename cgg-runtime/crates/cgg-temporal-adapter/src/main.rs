use anyhow::{bail, Context, Result};
use cgg_temporal_adapter::{
    build_invocation_payload, normalize_proposal, prepare_request, CanonicalMountEnvelope,
    OutputAuthorityV1, PrepareRequestInput, SplatInterpretationRequestV1,
};
use serde::de::DeserializeOwned;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const DEFAULT_MOUNT_TIMEOUT_SECS: u64 = 120;
const MAX_MOUNT_TIMEOUT_SECS: u64 = 3_600;
static TEMP_SEQUENCE: AtomicU64 = AtomicU64::new(0);

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
    let payload_file = TempArtifact::write("payload", payload.as_bytes())?;
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
        .arg("--payload-file")
        .arg(payload_file.path());
    if let Ok(originator) = std::env::var("CANONICAL_MOUNT_ORIGINATOR") {
        command.arg("--originator").arg(originator);
    }
    let output = run_with_timeout(&mut command, mount_timeout()?)
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

struct TempArtifact {
    path: PathBuf,
}

impl TempArtifact {
    fn write(label: &str, bytes: &[u8]) -> Result<Self> {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        for _ in 0..32 {
            let sequence = TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "cgg-temporal-{label}-{}-{stamp}-{sequence}",
                std::process::id()
            ));
            let mut options = OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            match options.open(&path) {
                Ok(mut file) => {
                    file.write_all(bytes)
                        .with_context(|| format!("failed to write {}", path.display()))?;
                    file.flush()
                        .with_context(|| format!("failed to flush {}", path.display()))?;
                    return Ok(Self { path });
                }
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => {
                    return Err(error)
                        .with_context(|| format!("failed to create {}", path.display()))
                }
            }
        }
        bail!("failed to allocate a unique temporal adapter artifact")
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempArtifact {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

struct MountOutput {
    status: ExitStatus,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

fn mount_timeout() -> Result<Duration> {
    let raw = match std::env::var("CGG_TEMPORAL_MOUNT_TIMEOUT_SECS") {
        Ok(value) => value,
        Err(std::env::VarError::NotPresent) => {
            return Ok(Duration::from_secs(DEFAULT_MOUNT_TIMEOUT_SECS))
        }
        Err(error) => return Err(error).context("failed to read mount timeout"),
    };
    let seconds = raw
        .parse::<u64>()
        .with_context(|| format!("CGG_TEMPORAL_MOUNT_TIMEOUT_SECS is not an integer: {raw:?}"))?;
    if !(1..=MAX_MOUNT_TIMEOUT_SECS).contains(&seconds) {
        bail!(
            "CGG_TEMPORAL_MOUNT_TIMEOUT_SECS must be between 1 and {MAX_MOUNT_TIMEOUT_SECS}"
        );
    }
    Ok(Duration::from_secs(seconds))
}

fn run_with_timeout(command: &mut Command, timeout: Duration) -> Result<MountOutput> {
    let stdout_file = TempArtifact::write("stdout", b"")?;
    let stderr_file = TempArtifact::write("stderr", b"")?;
    let stdout = OpenOptions::new()
        .write(true)
        .truncate(true)
        .open(stdout_file.path())
        .context("failed to open canonical-mount stdout artifact")?;
    let stderr = OpenOptions::new()
        .write(true)
        .truncate(true)
        .open(stderr_file.path())
        .context("failed to open canonical-mount stderr artifact")?;

    let mut child = command
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .context("failed to spawn canonical-mount")?;
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child
            .try_wait()
            .context("failed while waiting for canonical-mount")?
        {
            break status;
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            bail!(
                "canonical-mount timed out after {} seconds",
                timeout.as_secs()
            );
        }
        thread::sleep(Duration::from_millis(25));
    };

    let stdout = fs::read(stdout_file.path())
        .context("failed to read canonical-mount stdout artifact")?;
    let stderr = fs::read(stderr_file.path())
        .context("failed to read canonical-mount stderr artifact")?;
    Ok(MountOutput {
        status,
        stdout,
        stderr,
    })
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
        both independent bindings, and emit the normalized proposal. Payload bytes
        travel through a protected temporary file, never argv. The optional
        CANONICAL_MOUNT_ORIGINATOR environment variable selects an admitted originator;
        CGG_TEMPORAL_MOUNT_TIMEOUT_SECS sets a 1..=3600 second deadline (default 120).

The downstream homeskillet kernel consumes the generic protocol. It has no CGG
dependency and receives no untyped field hydration.
"#
    );
}
