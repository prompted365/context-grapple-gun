use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

pub const PROTOCOL_SCHEMA_SHA256: &str =
    "42e4f35f9b7a8c0f6ec82529ea71948c1ab33f51174adb93fa07b21316fa2e75";
pub const REQUEST_CONTRACT: &str = "splat.interpretation-request.v1";
pub const PROPOSAL_CONTRACT: &str = "splat.proposal-envelope.v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TemporalCoordinateV1 {
    pub global_tic: u64,
    #[serde(default)]
    pub causal_frontier: BTreeMap<String, u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorldKindV1 {
    Actual,
    Reconstructed,
    Counterfactual,
    Forecast,
    Conditional,
    Target,
    Adversarial,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceTenseV1 {
    CanonicalIntent,
    RuntimeObservation,
    RuntimeAssertion,
    CompiledAtGeneration,
    Reconstructed,
    Simulated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OutputAuthorityV1 {
    Evidence,
    Advisory,
    Proposal,
    Proposing,
    Reasoning,
    DelegatedExecution,
    AdmittedMutation,
}

impl OutputAuthorityV1 {
    pub fn allows(self, observed: Self) -> bool {
        observed <= self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LaneV1 {
    pub name: String,
    pub class: LaneClassV1,
    pub scope: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LaneClassV1 {
    Epistemic,
    Authority,
    World,
    Execution,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReceiptRefV1 {
    pub id: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceRefV1 {
    pub name: String,
    pub content_hash: String,
    pub source_tense: SourceTenseV1,
    pub authority: OutputAuthorityV1,
    pub current: bool,
    #[serde(default)]
    pub receipts: Vec<ReceiptRefV1>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct StatusAxesV1 {
    pub covenant_status: Option<CovenantStatusV1>,
    pub projection_status: Option<ProjectionStatusV1>,
    pub conformation_status: Option<ConformationStatusV1>,
    pub execution_status: Option<ExecutionStatusV1>,
    pub evidence_status: Option<EvidenceStatusV1>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CovenantStatusV1 {
    Absent,
    Incomplete,
    Admitted,
    Fulfilled,
    Superseded,
    Invalidated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProjectionStatusV1 {
    Complete,
    Partial,
    Lost,
    Conflicting,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConformationStatusV1 {
    Current,
    Stale,
    Contradicted,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionStatusV1 {
    Ready,
    BlockedByDependency,
    BlockedByRuntime,
    BlockedByPhysics,
    Parked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceStatusV1 {
    NotRequiredForApprovedMechanic,
    InheritedFromAdmission,
    SupportedByScars,
    Supported,
    Verified,
    RequiresCurrentProbe,
    GenuinelyInsufficient,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CenterExclusionV1 {
    pub protected: bool,
    pub declaration: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceStatusV1 {
    pub state: SourceStatusStateV1,
    pub reason: Option<String>,
    pub content_hash: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceStatusStateV1 {
    Loaded,
    Unavailable,
    Malformed,
    Stale,
    Contradicted,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CovenantSliceEnvelopeV1 {
    pub slice_type: String,
    pub identity: serde_json::Value,
    pub covenant_ref: Option<String>,
    pub admission_receipt: Option<ReceiptRefV1>,
    pub reality_state: serde_json::Value,
    pub target_state: serde_json::Value,
    #[serde(default)]
    pub source_status: BTreeMap<String, SourceStatusV1>,
    pub status_axes: StatusAxesV1,
    pub source_tense: SourceTenseV1,
    #[serde(default)]
    pub input_hashes: BTreeMap<String, Option<String>>,
    pub operative_tic: Option<u64>,
    pub center_exclusion: CenterExclusionV1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InterpretationOperationV1 {
    Splat,
    Simulate,
    Verify,
    ProposeMorphism,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SplatInterpretationRequestV1 {
    pub contract: String,
    pub request_id: String,
    pub coordinate: TemporalCoordinateV1,
    pub branch_id: String,
    pub world_kind: WorldKindV1,
    pub covenant_id: String,
    pub covenant_hash: String,
    pub admission_receipt: ReceiptRefV1,
    pub covenant_slice: CovenantSliceEnvelopeV1,
    pub slice_hash: String,
    pub authority_ceiling: OutputAuthorityV1,
    pub requested_operation: InterpretationOperationV1,
    pub terminalized: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum FacetNameV1 {
    #[serde(rename = "KAT")]
    Kat,
    #[serde(rename = "APO")]
    Apo,
    #[serde(rename = "PAR")]
    Par,
    #[serde(rename = "PLE")]
    Ple,
    #[serde(rename = "ENA")]
    Ena,
    #[serde(rename = "TEL")]
    Tel,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FacetAssertionV1 {
    pub statement: String,
    pub lane: LaneV1,
    pub world_kind: WorldKindV1,
    pub authority: OutputAuthorityV1,
    #[serde(default)]
    pub sources: Vec<SourceRefV1>,
    #[serde(default)]
    pub receipts: Vec<ReceiptRefV1>,
    pub confidence: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FacetReadV1 {
    pub facet: FacetNameV1,
    pub assertions: Vec<FacetAssertionV1>,
    #[serde(default)]
    pub constraints: Vec<String>,
    #[serde(default)]
    pub contradictions: Vec<String>,
    #[serde(default)]
    pub working_centroid_refs: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[allow(non_snake_case)]
pub struct SixFacetRecordV1 {
    pub KAT: FacetReadV1,
    pub APO: FacetReadV1,
    pub PAR: FacetReadV1,
    pub PLE: FacetReadV1,
    pub ENA: FacetReadV1,
    pub TEL: FacetReadV1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DispositionKindV1 {
    Narrowed,
    Excluded,
    Disproven,
    Suspended,
    Deferred,
    DeConsidered,
    Localized,
    LeftOpen,
    LiveUnderCondition,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DispositionV1 {
    pub item: String,
    pub kind: DispositionKindV1,
    pub lane: LaneV1,
    pub condition: Option<String>,
    #[serde(default)]
    pub reasons: Vec<String>,
    #[serde(default)]
    pub receipts: Vec<ReceiptRefV1>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum ExecutionExprV1 {
    Leaf {
        route_id: String,
        title: String,
        objectives: Vec<String>,
    },
    #[serde(rename = "seq")]
    Sequential {
        operands: Vec<ExecutionExprV1>,
    },
    Parallel {
        operands: Vec<ExecutionExprV1>,
    },
    Choice {
        operands: Vec<ExecutionExprV1>,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MorphismProposalV1 {
    pub proposal_id: String,
    pub model_id: String,
    pub generated_at: TemporalCoordinateV1,
    pub facets: SixFacetRecordV1,
    pub execution: Option<ExecutionExprV1>,
    #[serde(default)]
    pub assumptions: Vec<String>,
    #[serde(default)]
    pub refusals: Vec<String>,
    #[serde(default)]
    pub unresolved: Vec<String>,
    pub uncertainty: f64,
    pub output_authority: OutputAuthorityV1,
    pub terminalized: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InterpreterIdentityV1 {
    pub adapter: String,
    pub adapter_version: String,
    pub harness: String,
    pub originator: String,
    pub model: String,
    #[serde(default)]
    pub provider_receipts: Vec<ReceiptRefV1>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OriginatorRequestBindingV1 {
    pub request_id: String,
    pub request_hash: String,
    pub covenant_id: String,
    pub covenant_hash: String,
    pub slice_hash: String,
    pub admission_receipt: ReceiptRefV1,
    pub coordinate: TemporalCoordinateV1,
    pub authority_ceiling: OutputAuthorityV1,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OriginatorInvocationBindingV1 {
    pub invocation_payload_sha256: String,
    pub result_text_sha256: String,
    pub executable_name: String,
    pub executable_version: String,
    pub executable_source_commit: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ChoiceBranchV1 {
    L,
    R,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SplatProposalEnvelopeV1 {
    pub contract: String,
    pub request_id: String,
    pub request_hash: String,
    pub covenant_id: String,
    pub admission_receipt: ReceiptRefV1,
    pub authority: OutputAuthorityV1,
    pub interpreter: InterpreterIdentityV1,
    pub originator_echo: OriginatorRequestBindingV1,
    pub originator_binding: OriginatorInvocationBindingV1,
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
    pub terminalized: bool,
}

pub fn hash_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

pub fn hash_serializable<T: Serialize>(
    domain: &str,
    value: &T,
) -> Result<String, serde_json::Error> {
    let bytes = serde_json::to_vec(value)?;
    let mut hasher = Sha256::new();
    hasher.update(domain.as_bytes());
    hasher.update(b"\n");
    hasher.update(bytes);
    Ok(hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect())
}

pub fn slice_hash(slice: &CovenantSliceEnvelopeV1) -> Result<String, serde_json::Error> {
    hash_serializable("splat.covenant-slice.v1", slice)
}

pub fn request_hash(request: &SplatInterpretationRequestV1) -> Result<String, serde_json::Error> {
    hash_serializable(REQUEST_CONTRACT, request)
}
