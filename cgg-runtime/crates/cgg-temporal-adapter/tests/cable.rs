use cgg_temporal_adapter::*;
use serde_json::json;
use std::collections::BTreeMap;
use std::process::Command;

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

fn request_binding(request: &SplatInterpretationRequestV1) -> OriginatorRequestBindingV1 {
    OriginatorRequestBindingV1 {
        request_id: request.request_id.clone(),
        request_hash: request_hash(request).unwrap(),
        covenant_id: request.covenant_id.clone(),
        covenant_hash: request.covenant_hash.clone(),
        slice_hash: request.slice_hash.clone(),
        admission_receipt: request.admission_receipt.clone(),
        coordinate: request.coordinate.clone(),
        authority_ceiling: request.authority_ceiling,
    }
}

fn interpretation(request: &SplatInterpretationRequestV1) -> InterpretationResultV1 {
    InterpretationResultV1 {
        request_binding: request_binding(request),
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

fn payload(request: &SplatInterpretationRequestV1) -> String {
    build_invocation_payload(request).unwrap()
}

fn mount(request: &SplatInterpretationRequestV1, payload: &str) -> CanonicalMountEnvelope {
    let text = serde_json::to_string(&interpretation(request)).unwrap();
    CanonicalMountEnvelope {
        command: "invoke".to_string(),
        office: "ent_homeskillet".to_string(),
        lane: "temporal-splat".to_string(),
        work_class: "reasoning".to_string(),
        originator: "frontier".to_string(),
        backend: "frontier".to_string(),
        output_authority: OutputAuthorityV1::Proposal,
        report: CanonicalMountReport {
            text: text.clone(),
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
        invocation_binding: CanonicalMountInvocationBinding {
            contract: "canonical-mount.invocation-binding.v1".to_string(),
            payload_sha256: hash_bytes(payload.as_bytes()),
            report_text_sha256: hash_bytes(text.as_bytes()),
            request_hash: Some(request_hash(request).unwrap()),
            tic: request.coordinate.global_tic as i64,
            executable: CanonicalMountExecutableIdentity {
                name: "canonical-mount".to_string(),
                version: "0.0.1".to_string(),
                source_commit: "e".repeat(40),
            },
        },
        provider_error: None,
        exit_status: 0,
        terminalized: false,
    }
}

fn replace_result(
    request: &SplatInterpretationRequestV1,
    payload: &str,
    result: InterpretationResultV1,
) -> CanonicalMountEnvelope {
    let mut envelope = mount(request, payload);
    envelope.report.text = serde_json::to_string(&result).unwrap();
    envelope.invocation_binding.report_text_sha256 = hash_bytes(envelope.report.text.as_bytes());
    envelope
}

#[test]
fn hydrated_slice_is_bound_to_admission_and_tic() {
    let request = prepared();
    validate_request(&request).unwrap();
    assert_eq!(request.world_kind, WorldKindV1::Actual);
    assert_eq!(
        request.covenant_slice.covenant_ref.as_deref(),
        Some("cov-a")
    );
    assert!(!request.terminalized);
}

#[test]
fn canonical_mount_output_normalizes_to_exact_request_hash() {
    let request = prepared();
    let payload = payload(&request);
    let proposal = normalize_proposal(&request, &payload, mount(&request, &payload)).unwrap();
    assert_eq!(proposal.request_hash, request_hash(&request).unwrap());
    assert_eq!(proposal.originator_echo, request_binding(&request));
    assert_eq!(
        proposal.originator_binding.invocation_payload_sha256,
        hash_bytes(payload.as_bytes())
    );
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
    let payload = payload(&request);
    let mut envelope = mount(&request, &payload);
    envelope.civic_receipt.terminalized = true;
    assert!(matches!(
        normalize_proposal(&request, &payload, envelope),
        Err(AdapterError::Mount(_))
    ));
}

#[test]
fn authority_widening_is_rejected() {
    let request = prepared();
    let payload = payload(&request);
    let mut result = interpretation(&request);
    result.proposal.output_authority = OutputAuthorityV1::AdmittedMutation;
    let envelope = replace_result(&request, &payload, result);
    assert!(matches!(
        normalize_proposal(&request, &payload, envelope),
        Err(AdapterError::Authority(_))
    ));
}

#[test]
fn normalize_rechecks_the_admitted_covenant_axis() {
    let mut request = prepared();
    let payload = payload(&request);
    request.covenant_slice.status_axes.covenant_status = Some(CovenantStatusV1::Superseded);
    request.slice_hash = slice_hash(&request.covenant_slice).unwrap();
    assert!(matches!(
        normalize_proposal(&request, &payload, mount(&request, &payload)),
        Err(AdapterError::Authority(_))
    ));
}

#[test]
fn mount_and_embedded_proposal_authority_must_agree() {
    let mut request = prepared();
    request.authority_ceiling = OutputAuthorityV1::Reasoning;
    let payload = payload(&request);
    let mut result = interpretation(&request);
    result.proposal.output_authority = OutputAuthorityV1::Proposal;
    let mut envelope = replace_result(&request, &payload, result);
    envelope.output_authority = OutputAuthorityV1::Advisory;
    envelope.civic_receipt.output_authority = OutputAuthorityV1::Advisory;
    assert!(matches!(
        normalize_proposal(&request, &payload, envelope),
        Err(AdapterError::Authority(_))
    ));
}

#[test]
fn facet_assertions_cannot_widen_authority_inside_a_valid_proposal() {
    let request = prepared();
    let payload = payload(&request);
    let mut result = interpretation(&request);
    result.proposal.facets.KAT.assertions[0].authority = OutputAuthorityV1::AdmittedMutation;
    let envelope = replace_result(&request, &payload, result);
    assert!(matches!(
        normalize_proposal(&request, &payload, envelope),
        Err(AdapterError::Authority(_))
    ));
}

#[test]
fn originator_output_from_another_request_cannot_be_rebound() {
    let request_a = prepared();
    let payload_a = payload(&request_a);
    let mut request_b = prepared();
    request_b.request_id = "request-b".to_string();
    let payload_b = payload(&request_b);
    let mut envelope = mount(&request_a, &payload_a);
    envelope.invocation_binding.payload_sha256 = hash_bytes(payload_b.as_bytes());
    envelope.invocation_binding.request_hash = Some(request_hash(&request_b).unwrap());
    assert!(matches!(
        normalize_proposal(&request_b, &payload_b, envelope),
        Err(AdapterError::Proposal(_))
    ));
}

#[test]
fn exact_payload_and_report_bytes_are_recomputed() {
    let request = prepared();
    let payload = payload(&request);
    let mut bad_payload = mount(&request, &payload);
    bad_payload.invocation_binding.payload_sha256 = "f".repeat(64);
    assert!(matches!(
        normalize_proposal(&request, &payload, bad_payload),
        Err(AdapterError::Mount(_))
    ));

    let mut bad_report = mount(&request, &payload);
    bad_report.report.text.push(' ');
    assert!(matches!(
        normalize_proposal(&request, &payload, bad_report),
        Err(AdapterError::Mount(_))
    ));
}

#[test]
fn mount_executable_must_carry_an_exact_source_commit() {
    let request = prepared();
    let payload = payload(&request);
    let mut envelope = mount(&request, &payload);
    envelope.invocation_binding.executable.source_commit = "unknown".to_string();
    assert!(matches!(
        normalize_proposal(&request, &payload, envelope),
        Err(AdapterError::GitCommit { .. })
    ));
}

#[test]
fn exact_canonical_mount_binary_closes_binding() {
    let Ok(mount_bin) = std::env::var("CANONICAL_MOUNT_BIN") else {
        eprintln!("explicit cross-repository canary not configured; unit lane only");
        return;
    };
    let expected_commit = std::env::var("CANONICAL_MOUNT_EXPECTED_COMMIT")
        .expect("cross-repository canary must pin the mount commit");
    let request = prepared();
    let exact_payload = payload(&request);
    let exact_report = serde_json::to_string(&interpretation(&request)).unwrap();
    let output = Command::new(mount_bin)
        .args([
            "invoke",
            "--office",
            "ent_homeskillet",
            "--lane",
            "temporal-splat",
            "--work-class",
            "reasoning",
            "--output-authority",
            "proposal",
            "--originator",
            "mock",
            "--tic",
            "635",
            "--payload",
            &exact_payload,
        ])
        .env("ALLOW_MOCK_ENGINE", "1")
        .env("CANONICAL_MOUNT_MOCK_REPORT_TEXT", &exact_report)
        .output()
        .expect("spawn exact canonical-mount binary");
    assert!(
        output.status.success(),
        "canonical-mount failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let mount: CanonicalMountEnvelope =
        serde_json::from_slice(&output.stdout).expect("typed canonical-mount output");
    assert_eq!(
        mount.invocation_binding.executable.source_commit,
        expected_commit
    );
    let proposal = normalize_proposal(&request, &exact_payload, mount)
        .expect("exact live binary binding must normalize");
    assert_eq!(proposal.request_hash, request_hash(&request).unwrap());
    assert_eq!(
        proposal.originator_binding.executable_source_commit,
        expected_commit
    );
    assert!(!proposal.terminalized);
}

#[test]
fn emit_cross_repository_protocol_fixture_when_requested() {
    let Ok(directory) = std::env::var("CGG_CROSS_FIXTURE_DIR") else {
        return;
    };
    let request = prepared();
    let exact_payload = payload(&request);
    let proposal =
        normalize_proposal(&request, &exact_payload, mount(&request, &exact_payload)).unwrap();
    let directory = std::path::PathBuf::from(directory);
    std::fs::create_dir_all(&directory).unwrap();
    std::fs::write(
        directory.join("request.json"),
        serde_json::to_vec_pretty(&request).unwrap(),
    )
    .unwrap();
    std::fs::write(
        directory.join("proposal.json"),
        serde_json::to_vec_pretty(&proposal).unwrap(),
    )
    .unwrap();
}
