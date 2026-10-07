from datetime import UTC, datetime

import pytest

from driftguard.models.core import (
    ContractCandidate,
    UsageRecord,
    Verdict,
    VerdictTier,
    make_contract_id,
)
from driftguard.models.transitions import CONTRACT_TRANSITIONS, can_transition


@pytest.fixture
def valid_candidate_dict() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "vendor": "stripe",
        "product": "api",
        "change_type": "removal",
        "surface": {
            "kind": "endpoint",
            "ref": "stripe:api:endpoint:v1_charges_create"
        },
        "before": None,
        "after": None,
        "effective": {
            "announced_at": "2024-01-01",
            "effective_at": "2024-06-01",
            "enforcement": "hard"
        },
        "scope_conditions": [],
        "required_action": {
            "action": "migrate",
            "text": "Use PaymentIntents"
        },
        "evidence": [{
            "quote": "Charges API is being removed.",
            "source_url": "https://stripe.com/docs/upgrades",
            "entry_id": "123"
        }]
    }

def test_contract_valid_parse(valid_candidate_dict: dict[str, object]) -> None:
    cand = ContractCandidate(**valid_candidate_dict) # type: ignore
    assert cand.vendor == "stripe"
    assert cand.before is None

def test_contract_unknown_field_rejected(valid_candidate_dict: dict[str, object]) -> None:
    valid_candidate_dict["made_up_field"] = "bad"
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict) # type: ignore

def test_contract_missing_evidence_rejected(valid_candidate_dict: dict[str, object]) -> None:
    valid_candidate_dict["evidence"] = []
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict) # type: ignore

def test_contract_quote_length_rejected(valid_candidate_dict: dict[str, object]) -> None:
    ev: list[dict[str, str]] = valid_candidate_dict["evidence"] # type: ignore
    ev[0]["quote"] = "a" * 501
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict) # type: ignore

def test_bad_ontology_ref_rejected(valid_candidate_dict: dict[str, object]) -> None:
    surf: dict[str, str] = valid_candidate_dict["surface"] # type: ignore
    surf["ref"] = "bad-ref-no-colons"
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict) # type: ignore

def test_make_contract_id_deterministic() -> None:
    id1 = make_contract_id("v", "p", "v:p:endpoint:foo", "removal", "2024-01-01", "1")
    id2 = make_contract_id("v", "p", "v:p:endpoint:foo", "removal", "2024-01-01", "1")
    id3 = make_contract_id("v", "p", "v:p:endpoint:foo", "removal", "2024-01-02", "1")
    assert id1 == id2
    assert id1 != id3
    assert "endpoint" in id1

def test_lifecycle_transitions() -> None:
    # Test allowed
    for state, allowed in CONTRACT_TRANSITIONS.items():
        for next_st in allowed:
            assert can_transition("contract", state.value, next_st.value)
    
    # Test forbidden
    assert not can_transition("contract", "NEW", "ACTIVE")
    assert not can_transition("impact", "DETECTED", "VERIFYING")

def test_usage_record_no_source_text_fields() -> None:
    banned = ["source", "snippet", "text", "code"]
    for field_name in UsageRecord.model_fields:
        for b in banned:
            assert b not in field_name.lower()

def test_usage_record_confidence() -> None:
    base = {
        "repo": "x", "commit_sha": "y", "file": "z", "line": 1, 
        "symbol": "a", "vendor": "v", "surface_ref": "v:p:k:n", 
        "kind": "call", "detector": "rule"
    }
    UsageRecord(**base, confidence=1.0) # type: ignore
    with pytest.raises(ValueError):
        UsageRecord(**base, confidence=1.5) # type: ignore

def test_verdict_limitations() -> None:
    base = {
        "evidence_refs": {"baseline": "1", "mutated": "2", "post_fix": "3", "probe": "4"},
        "generated_at": datetime.now(UTC)
    }
    with pytest.raises(ValueError):
        Verdict(**base, tier=VerdictTier.V1, limitations="") # type: ignore
    
    # V4 doesn't require limitations
    Verdict(**base, tier=VerdictTier.V4, limitations="") # type: ignore