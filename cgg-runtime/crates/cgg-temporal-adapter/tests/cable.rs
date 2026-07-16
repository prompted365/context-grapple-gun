use cgg_temporal_adapter::*;
use serde_json::json;
use std::collections::BTreeMap;

fn receipt(id: &str) -> ReceiptRefV1 {
    ReceiptRefV1 {
        id: id.to_string(),
        sha256: "a".repeat(64),
    }
}

fn axes() -> StatusAxesV1 {
    StatusAxesV1 {
        covenant_status: Some(CovenantStatusV1::Admitted),
        projection_status: Some(ProjectionStatusV1::Complete),
        conformation_status: Some(ConformationStatusV1::Current),
        execution_status: Some(ExecutionStatusV1::Ready),
        evidence_status: Some(EvidenceStatusV1::InheritedFromAdmission),
    }
}

fn prepared() -> SplatInterpretationRequestV1 {
    prepare_request(PrepareRequestInput {
        request_id: "request-a".to_string(),
        coordinate: TemporalCoordinateV1 {
            global_tic: 635,
            causal_frontier: BTreeMap::new(),
        },
        branch_id: "actual".to_string(),
        covenant_id: "cov-a".to_string(),
        covenant_hash: "b".repeat(64),
        admission_receipt: receipt("admission"),
        hydrated_slice: json!({
            "slice_type": "CovenantSlice-scaffold/v2-tic622",
            "identity": {"backlog_id":"route-a"},
            "reality_state": {"runtime":"current"},
            "target_state": {"target":"done"},
            "source_status": {
                "backlog": {"state":"loaded"},
                "board": {"state":"loaded"}
            },
            "source_tense": "compiled-at-generation",
            "input_hashes": {
                "board-state.json": "c".repeat(64),
                "optional.json": null
            },
            "operative_tic": 635
        }),
        status_axes: axes(),
        authority_ceiling: OutputAuthorityV1::Proposal,
        requested_operation: InterpretationOperationV1::Splat,
        center_exclusion_declaration:
            "held-open center is not a target, route, vertex, or model output".to_string(),
    })
    .unwrap()
}

fn lane() -> LaneV1 {
    LaneV1 {
        name: "runtime".to_string(),
        class: LaneClassV1::Execution,
        scope: "route-a".to_string(),
    }
}

fn read(facet: FacetNameV1) -> FacetReadV1 {
    FacetReadV1 {
        facet,
        assertions: vec![FacetAssertionV1 {
            statement: format!("{facet:?} assertion"),
            lane: lane(),
            world_kind: WorldKindV1::Actual,
            authority: OutputAuthorityV1::Evidence,
            sources: vec![SourceRefV1 {
                name: "board".to_string(),
                content_hash: "d".repeat(64),
                source_tense: SourceTenseV1::RuntimeObservation,
                authority: OutputAuthorityV1::Evidence,
                current: true,
                receipts: vec![receipt("source")],
            }],
            receipts: vec![receipt("facet")],
            confidence: 0.8,
        }],
        constraints: Vec::new(),
        contradictions: Vec::new(),
        working_centroid_refs: vec![format!("{facet:?}-working")],
    }
}

fn interpretation(request: &SplatInterpretationRequestV1) -> InterpretationResultV1 {
    InterpretationResultV1 {
        proposal: MorphismProposalV1 {
            proposal_id: "proposal-a".to_string(),
            model_id: "model-a".to_string(),
            generated_at: request.coordinate.clone(),
            facets: SixFacetRecordV1 {
                KAT: read(FacetNameV1::Kat),
                APO: read(FacetNameV1::Apo),
                PAR: read(FacetNameV1::Par),
                PLE: read(FacetNameV1::Ple),
                ENA: read(FacetNameV1::Ena),
                TEL: read(FacetNameV1::Tel),
            },
            execution: Some(ExecutionExprV1::Leaf {
                route_id: "route-a".to_string(),
                title: "route".to_string(),
                objectives: vec!["build".to_string()],
            }),
            assumptions: Vec::new(),
            refusals: Vec::new(),
            unresolved: Vec::new(),
            uncertainty: 0.2,
            output_authority: OutputAuthorityV1::Proposal,
            terminalized: false,
        },
        dispositions: Vec::new(),
        renarrow_triggers: vec!["source hash changes".to_string()],
        selected_choices: BTreeMap::new(),
        write_surfaces: vec!["repo:route-a".to_string()],
        rollback_contract: "reverse topological drill".to_string(),
    }
}

fn mount(request: &SplatInterpretationRequestV1) -> CanonicalMountEnvelope {
    CanonicalMountEnvelope {
        command: "invoke".to_string(),
        office: "ent_homeskillet".to_string(),
        lane: "temporal-splat".to_string(),
        work_class: "reasoning".to_string(),
        originator: "frontier".to_string(),
        backend: "frontier".to_string(),
        output_authority: OutputAuthorityV1::Proposal,
        report: CanonicalMountReport {
            text: serde_json::to_string(&interpretation(request)).unwrap(),
            artifacts: Vec::new(),
            commands: Vec::new(),
            exits: vec![0],
        },
        civic_receipt: CivicReceipt {
            understood_scope: "bounded splat proposal".to_string(),
            invoked: true,
            output_authority: OutputAuthorityV1::Proposal,
            terminalized: false,
        },
        provider_error: None,
        exit_status: 0,
        terminalized: false,
    }
}

#[test]
fn hydrated_slice_is_bound_to_admission_and_tic() {
    let request = prepared();
    validate_request(&request).unwrap();
    assert_eq!(request.world_kind, WorldKindV1::Actual);
    assert_eq!(request.covenant_slice.covenant_ref.as_deref(), Some("cov-a"));
    assert!(!request.terminalized);
}

#[test]
fn canonical_mount_output_normalizes_to_exact_request_hash() {
    let request = prepared();
    let proposal = normalize_proposal(&request, mount(&request)).unwrap();
    assert_eq!(proposal.request_hash, request_hash(&request).unwrap());
    assert_eq!(proposal.interpreter.model, "model-a");
    assert!(!proposal.terminalized);
}

#[test]
fn changed_tic_refuses_before_model_invocation() {
    let mut request = prepared();
    request.coordinate.global_tic = 636;
    assert!(matches!(
        validate_request(&request),
        Err(AdapterError::Currentness(_))
    ));
}

#[test]
fn terminalization_claim_is_rejected() {
    let request = prepared();
    let mut envelope = mount(&request);
    envelope.civic_receipt.terminalized = true;
    assert!(matches!(
        normalize_proposal(&request, envelope),
        Err(AdapterError::Mount(_))
    ));
}

#[test]
fn authority_widening_is_rejected() {
    let request = prepared();
    let mut result = interpretation(&request);
    result.proposal.output_authority = OutputAuthorityV1::AdmittedMutation;
    let mut envelope = mount(&request);
    envelope.report.text = serde_json::to_string(&result).unwrap();
    assert!(matches!(
        normalize_proposal(&request, envelope),
        Err(AdapterError::Authority(_))
    ));
}
