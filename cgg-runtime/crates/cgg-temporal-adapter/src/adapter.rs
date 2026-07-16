use crate::protocol::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use thiserror::Error;

pub const ADAPTER_ID: &str = "cgg-temporal-adapter";
pub const ADAPTER_VERSION: &str = "0.1.0";

#[derive(Debug, Error)]
pub enum AdapterError {
    #[error("required field {0} is absent or empty")]
    Missing(&'static str),
    #[error("field {field} must be a lowercase SHA-256 digest, got {value:?}")]
    Sha256 { field: &'static str, value: String },
    #[error("hydrated CovenantSlice is malformed: {0}")]
    Slice(String),
    #[error("currentness refusal: {0}")]
    Currentness(String),
    #[error("authority refusal: {0}")]
    Authority(String),
    #[error("canonical-mount refusal: {0}")]
    Mount(String),
    #[error("proposal refusal: {0}")]
    Proposal(String),
    #[error("JSON failed: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrepareRequestInput {
    pub request_id: String,
    pub coordinate: TemporalCoordinateV1,
    pub branch_id: String,
    pub covenant_id: String,
    pub covenant_hash: String,
    pub admission_receipt: ReceiptRefV1,
    pub hydrated_slice: Value,
    pub status_axes: StatusAxesV1,
    pub authority_ceiling: OutputAuthorityV1,
    pub requested_operation: InterpretationOperationV1,
    pub center_exclusion_declaration: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanonicalMountReport {
    pub text: String,
    #[serde(default)]
    pub artifacts: Vec<String>,
    #[serde(default)]
    pub commands: Vec<String>,
    #[serde(default)]
    pub exits: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CivicReceipt {
    pub understood_scope: String,
    pub invoked: bool,
    pub output_authority: OutputAuthorityV1,
    pub terminalized: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanonicalMountEnvelope {
    pub command: String,
    pub office: String,
    pub lane: String,
    pub work_class: String,
    pub originator: String,
    pub backend: String,
    pub output_authority: OutputAuthorityV1,
    pub report: CanonicalMountReport,
    pub civic_receipt: CivicReceipt,
    pub provider_error: Option<String>,
    pub exit_status: i64,
    pub terminalized: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterpretationResultV1 {
    pub proposal: MorphismProposalV1,
    #[serde(default)]
    pub dispositions: Vec<DispositionV1>,
    #[serde(default)]
    pub renarrow_triggers: Vec<String>,
    #[serde(default)]
    pub selected_choices: BTreeMap<String, ChoiceBranchV1>,
    #[serde(default)]
    pub write_surfaces: Vec<String>,
    pub rollback_contract: String,
}

pub fn prepare_request(
    input: PrepareRequestInput,
) -> Result<SplatInterpretationRequestV1, AdapterError> {
    nonempty("request_id", &input.request_id)?;
    nonempty("branch_id", &input.branch_id)?;
    nonempty("covenant_id", &input.covenant_id)?;
    nonempty(
        "center_exclusion_declaration",
        &input.center_exclusion_declaration,
    )?;
    valid_sha("covenant_hash", &input.covenant_hash)?;
    validate_receipt(&input.admission_receipt, "admission_receipt.sha256")?;

    if input.status_axes.covenant_status != Some(CovenantStatusV1::Admitted) {
        return Err(AdapterError::Authority(
            "interpretation request requires an admitted covenant axis".to_string(),
        ));
    }

    let object = input
        .hydrated_slice
        .as_object()
        .ok_or_else(|| AdapterError::Slice("root must be an object".to_string()))?;
    let identity = required_value(object, "identity")?.clone();
    let reality_state = required_value(object, "reality_state")?.clone();
    let target_state = required_value(object, "target_state")?.clone();
    let slice_type = required_str(object, "slice_type")?.to_string();
    let operative_tic = object.get("operative_tic").and_then(Value::as_u64);
    if operative_tic != Some(input.coordinate.global_tic) {
        return Err(AdapterError::Currentness(format!(
            "hydrated slice operative_tic {operative_tic:?} does not equal request tic {}",
            input.coordinate.global_tic
        )));
    }

    let source_tense = parse_source_tense(
        object
            .get("source_tense")
            .and_then(Value::as_str)
            .ok_or_else(|| AdapterError::Slice("source_tense is absent".to_string()))?,
    )?;
    let source_status = parse_source_status(object.get("source_status"))?;
    let input_hashes = parse_input_hashes(object.get("input_hashes"))?;

    let covenant_slice = CovenantSliceEnvelopeV1 {
        slice_type,
        identity,
        covenant_ref: Some(input.covenant_id.clone()),
        admission_receipt: Some(input.admission_receipt.clone()),
        reality_state,
        target_state,
        source_status,
        status_axes: input.status_axes,
        source_tense,
        input_hashes,
        operative_tic,
        center_exclusion: CenterExclusionV1 {
            protected: true,
            declaration: input.center_exclusion_declaration,
        },
    };
    let slice_hash = slice_hash(&covenant_slice)?;

    Ok(SplatInterpretationRequestV1 {
        contract: REQUEST_CONTRACT.to_string(),
        request_id: input.request_id,
        coordinate: input.coordinate,
        branch_id: input.branch_id,
        world_kind: WorldKindV1::Actual,
        covenant_id: input.covenant_id,
        covenant_hash: input.covenant_hash,
        admission_receipt: input.admission_receipt,
        covenant_slice,
        slice_hash,
        authority_ceiling: input.authority_ceiling,
        requested_operation: input.requested_operation,
        terminalized: false,
    })
}

pub fn normalize_proposal(
    request: &SplatInterpretationRequestV1,
    mount: CanonicalMountEnvelope,
) -> Result<SplatProposalEnvelopeV1, AdapterError> {
    validate_request(request)?;
    validate_mount(request, &mount)?;

    let result: InterpretationResultV1 = serde_json::from_str(mount.report.text.trim())
        .map_err(|error| AdapterError::Proposal(format!("report.text is not InterpretationResultV1: {error}")))?;
    validate_interpretation(request, &result)?;

    let provider_hash = hash_serializable("splat.canonical-mount-report.v1", &mount)?;
    let provider_receipt = ReceiptRefV1 {
        id: format!("canonical-mount-{provider_hash}"),
        sha256: provider_hash,
    };

    Ok(SplatProposalEnvelopeV1 {
        contract: PROPOSAL_CONTRACT.to_string(),
        request_id: request.request_id.clone(),
        request_hash: request_hash(request)?,
        covenant_id: request.covenant_id.clone(),
        admission_receipt: request.admission_receipt.clone(),
        authority: mount.output_authority,
        interpreter: InterpreterIdentityV1 {
            adapter: ADAPTER_ID.to_string(),
            adapter_version: ADAPTER_VERSION.to_string(),
            harness: "canonical-mount".to_string(),
            originator: mount.originator,
            model: result.proposal.model_id.clone(),
            provider_receipts: vec![provider_receipt],
        },
        proposal: result.proposal,
        dispositions: result.dispositions,
        renarrow_triggers: result.renarrow_triggers,
        selected_choices: result.selected_choices,
        write_surfaces: result.write_surfaces,
        rollback_contract: result.rollback_contract,
        terminalized: false,
    })
}

pub fn validate_request(request: &SplatInterpretationRequestV1) -> Result<(), AdapterError> {
    if request.contract != REQUEST_CONTRACT {
        return Err(AdapterError::Proposal(format!(
            "request contract {:?} is not {REQUEST_CONTRACT:?}",
            request.contract
        )));
    }
    if request.terminalized {
        return Err(AdapterError::Authority(
            "request claims terminalization".to_string(),
        ));
    }
    if request.world_kind != WorldKindV1::Actual {
        return Err(AdapterError::Currentness(
            "interpreter request must enter on the actual world".to_string(),
        ));
    }
    if request.coordinate.global_tic != request.covenant_slice.operative_tic.unwrap_or(u64::MAX) {
        return Err(AdapterError::Currentness(
            "request coordinate and slice tic disagree".to_string(),
        ));
    }
    if request.covenant_slice.covenant_ref.as_deref() != Some(request.covenant_id.as_str()) {
        return Err(AdapterError::Authority(
            "slice covenant_ref does not bind request covenant".to_string(),
        ));
    }
    if request.covenant_slice.admission_receipt.as_ref() != Some(&request.admission_receipt) {
        return Err(AdapterError::Authority(
            "slice admission receipt does not bind request receipt".to_string(),
        ));
    }
    if !request.covenant_slice.center_exclusion.protected {
        return Err(AdapterError::Authority(
            "held-open center is not protected".to_string(),
        ));
    }
    valid_sha("request.covenant_hash", &request.covenant_hash)?;
    valid_sha("request.slice_hash", &request.slice_hash)?;
    let actual_slice_hash = slice_hash(&request.covenant_slice)?;
    if actual_slice_hash != request.slice_hash {
        return Err(AdapterError::Proposal(format!(
            "slice hash mismatch: declared {}, computed {actual_slice_hash}",
            request.slice_hash
        )));
    }
    Ok(())
}

fn validate_mount(
    request: &SplatInterpretationRequestV1,
    mount: &CanonicalMountEnvelope,
) -> Result<(), AdapterError> {
    if mount.command != "invoke" {
        return Err(AdapterError::Mount(format!(
            "unexpected command {:?}",
            mount.command
        )));
    }
    if mount.terminalized || mount.civic_receipt.terminalized {
        return Err(AdapterError::Mount(
            "canonical-mount envelope claims terminalization".to_string(),
        ));
    }
    if !mount.civic_receipt.invoked {
        return Err(AdapterError::Mount(
            "canonical-mount did not invoke an originator".to_string(),
        ));
    }
    if mount.exit_status != 0 || mount.provider_error.is_some() {
        return Err(AdapterError::Mount(format!(
            "provider failed: exit_status={}, provider_error={:?}",
            mount.exit_status, mount.provider_error
        )));
    }
    if mount.report.text.trim().is_empty() {
        return Err(AdapterError::Mount("report.text is empty".to_string()));
    }
    if mount.civic_receipt.understood_scope.trim().is_empty() {
        return Err(AdapterError::Mount(
            "civic receipt understood_scope is empty".to_string(),
        ));
    }
    if mount.output_authority != mount.civic_receipt.output_authority {
        return Err(AdapterError::Mount(
            "top-level and civic output authority disagree".to_string(),
        ));
    }
    if !request.authority_ceiling.allows(mount.output_authority) {
        return Err(AdapterError::Authority(format!(
            "canonical-mount output authority {:?} exceeds request ceiling {:?}",
            mount.output_authority, request.authority_ceiling
        )));
    }
    Ok(())
}

fn validate_interpretation(
    request: &SplatInterpretationRequestV1,
    result: &InterpretationResultV1,
) -> Result<(), AdapterError> {
    if result.proposal.terminalized {
        return Err(AdapterError::Proposal(
            "model proposal claims terminalization".to_string(),
        ));
    }
    if result.proposal.generated_at != request.coordinate {
        return Err(AdapterError::Proposal(
            "proposal generated_at does not equal request coordinate".to_string(),
        ));
    }
    if !request
        .authority_ceiling
        .allows(result.proposal.output_authority)
    {
        return Err(AdapterError::Authority(format!(
            "proposal authority {:?} exceeds request ceiling {:?}",
            result.proposal.output_authority, request.authority_ceiling
        )));
    }
    if result.rollback_contract.trim().is_empty() {
        return Err(AdapterError::Proposal(
            "rollback_contract is empty".to_string(),
        ));
    }
    if !result.proposal.uncertainty.is_finite()
        || !(0.0..=1.0).contains(&result.proposal.uncertainty)
    {
        return Err(AdapterError::Proposal(
            "proposal uncertainty is outside [0,1]".to_string(),
        ));
    }
    validate_facets(&result.proposal.facets)?;
    Ok(())
}

fn validate_facets(facets: &SixFacetRecordV1) -> Result<(), AdapterError> {
    for (read, expected) in [
        (&facets.KAT, FacetNameV1::Kat),
        (&facets.APO, FacetNameV1::Apo),
        (&facets.PAR, FacetNameV1::Par),
        (&facets.PLE, FacetNameV1::Ple),
        (&facets.ENA, FacetNameV1::Ena),
        (&facets.TEL, FacetNameV1::Tel),
    ] {
        if read.facet != expected {
            return Err(AdapterError::Proposal(format!(
                "facet key expects {expected:?}, embedded facet is {:?}",
                read.facet
            )));
        }
        if read.assertions.is_empty() {
            return Err(AdapterError::Proposal(format!(
                "{expected:?} is empty"
            )));
        }
        for assertion in &read.assertions {
            if assertion.statement.trim().is_empty() {
                return Err(AdapterError::Proposal(format!(
                    "{expected:?} contains an empty assertion"
                )));
            }
            if !assertion.authority.allows(OutputAuthorityV1::Evidence)
                && assertion.authority != OutputAuthorityV1::Evidence
            {
                return Err(AdapterError::Authority(format!(
                    "{expected:?} assertion has invalid authority"
                )));
            }
            if !assertion.confidence.is_finite()
                || !(0.0..=1.0).contains(&assertion.confidence)
            {
                return Err(AdapterError::Proposal(format!(
                    "{expected:?} assertion confidence is outside [0,1]"
                )));
            }
            for source in &assertion.sources {
                valid_sha("facet.source.content_hash", &source.content_hash)?;
            }
            for receipt in &assertion.receipts {
                validate_receipt(receipt, "facet.receipt.sha256")?;
            }
        }
    }
    Ok(())
}

fn parse_source_tense(value: &str) -> Result<SourceTenseV1, AdapterError> {
    match value {
        "canonical-intent" | "canonical_intent" => Ok(SourceTenseV1::CanonicalIntent),
        "runtime-observation" | "runtime_observation" => Ok(SourceTenseV1::RuntimeObservation),
        "runtime-assertion" | "runtime_assertion" => Ok(SourceTenseV1::RuntimeAssertion),
        "compiled-at-generation" | "compiled_at_generation" => {
            Ok(SourceTenseV1::CompiledAtGeneration)
        }
        "reconstructed" => Ok(SourceTenseV1::Reconstructed),
        "simulated" => Ok(SourceTenseV1::Simulated),
        other => Err(AdapterError::Slice(format!(
            "unknown source_tense {other:?}"
        ))),
    }
}

fn parse_source_status(value: Option<&Value>) -> Result<BTreeMap<String, SourceStatusV1>, AdapterError> {
    let mut output = BTreeMap::new();
    let Some(object) = value.and_then(Value::as_object) else {
        return Err(AdapterError::Slice(
            "source_status must be an object".to_string(),
        ));
    };
    for (name, raw) in object {
        let raw = raw.as_object().ok_or_else(|| {
            AdapterError::Slice(format!("source_status[{name:?}] must be an object"))
        })?;
        let state = match raw.get("state").and_then(Value::as_str) {
            Some("loaded") => SourceStatusStateV1::Loaded,
            Some("unavailable") => SourceStatusStateV1::Unavailable,
            Some("malformed") => SourceStatusStateV1::Malformed,
            Some("stale") => SourceStatusStateV1::Stale,
            Some("contradicted") => SourceStatusStateV1::Contradicted,
            other => {
                return Err(AdapterError::Slice(format!(
                    "source_status[{name:?}].state is unsupported: {other:?}"
                )))
            }
        };
        let content_hash = raw
            .get("content_hash")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned);
        if let Some(hash) = &content_hash {
            valid_sha("source_status.content_hash", hash)?;
        }
        output.insert(
            name.clone(),
            SourceStatusV1 {
                state,
                reason: raw
                    .get("reason")
                    .and_then(Value::as_str)
                    .map(ToOwned::to_owned),
                content_hash,
            },
        );
    }
    Ok(output)
}

fn parse_input_hashes(value: Option<&Value>) -> Result<BTreeMap<String, Option<String>>, AdapterError> {
    let Some(object) = value.and_then(Value::as_object) else {
        return Err(AdapterError::Slice(
            "input_hashes must be an object".to_string(),
        ));
    };
    let mut output = BTreeMap::new();
    for (path, raw) in object {
        let hash = if raw.is_null() {
            None
        } else {
            let hash = raw.as_str().ok_or_else(|| {
                AdapterError::Slice(format!("input_hashes[{path:?}] must be string or null"))
            })?;
            valid_sha("input_hashes", hash)?;
            Some(hash.to_string())
        };
        output.insert(path.clone(), hash);
    }
    Ok(output)
}

fn required_value<'a>(
    object: &'a serde_json::Map<String, Value>,
    field: &'static str,
) -> Result<&'a Value, AdapterError> {
    object.get(field).ok_or(AdapterError::Missing(field))
}

fn required_str<'a>(
    object: &'a serde_json::Map<String, Value>,
    field: &'static str,
) -> Result<&'a str, AdapterError> {
    object
        .get(field)
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or(AdapterError::Missing(field))
}

fn validate_receipt(receipt: &ReceiptRefV1, field: &'static str) -> Result<(), AdapterError> {
    nonempty("receipt.id", &receipt.id)?;
    valid_sha(field, &receipt.sha256)
}

fn nonempty(field: &'static str, value: &str) -> Result<(), AdapterError> {
    if value.trim().is_empty() {
        Err(AdapterError::Missing(field))
    } else {
        Ok(())
    }
}

fn valid_sha(field: &'static str, value: &str) -> Result<(), AdapterError> {
    if value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        Ok(())
    } else {
        Err(AdapterError::Sha256 {
            field,
            value: value.to_string(),
        })
    }
}
