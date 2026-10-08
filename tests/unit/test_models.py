import subprocess
import sys
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
        "surface": {"kind": "endpoint", "ref": "stripe:api:endpoint:v1_charges_create"},
        "before": None,
        "after": None,
        "effective": {
            "announced_at": "2024-01-01",
            "effective_at": "2024-06-01",
            "enforcement": "hard",
        },
        "scope_conditions": [],
        "required_action": {"action": "migrate", "text": "Use PaymentIntents"},
        "evidence": [
            {
                "quote": "Charges API is being removed.",
                "source_url": "https://stripe.com/docs/upgrades",
                "entry_id": "123",
            }
        ],
    }


def test_contract_valid_parse(valid_candidate_dict: dict[str, object]) -> None:
    cand = ContractCandidate(**valid_candidate_dict)  # type: ignore
    assert cand.vendor == "stripe"
    assert cand.before is None


def test_contract_unknown_field_rejected(
    valid_candidate_dict: dict[str, object],
) -> None:
    valid_candidate_dict["made_up_field"] = "bad"
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict)  # type: ignore


def test_contract_missing_evidence_rejected(
    valid_candidate_dict: dict[str, object],
) -> None:
    valid_candidate_dict["evidence"] = []
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict)  # type: ignore


def test_contract_quote_length_rejected(
    valid_candidate_dict: dict[str, object],
) -> None:
    ev: list[dict[str, str]] = valid_candidate_dict["evidence"]  # type: ignore
    ev[0]["quote"] = "a" * 501
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict)  # type: ignore


def test_bad_ontology_ref_rejected(valid_candidate_dict: dict[str, object]) -> None:
    surf: dict[str, str] = valid_candidate_dict["surface"]  # type: ignore
    surf["ref"] = "bad-ref-no-colons"
    with pytest.raises(ValueError):
        ContractCandidate(**valid_candidate_dict)  # type: ignore


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
        "repo": "x",
        "commit_sha": "y",
        "file": "z",
        "line": 1,
        "symbol": "a",
        "vendor": "v",
        "surface_ref": "v:p:k:n",
        "kind": "call",
        "detector": "rule",
    }
    UsageRecord(**base, confidence=1.0)  # type: ignore
    with pytest.raises(ValueError):
        UsageRecord(**base, confidence=1.5)  # type: ignore


def test_verdict_limitations() -> None:
    base = {
        "evidence_refs": {
            "baseline": "1",
            "mutated": "2",
            "post_fix": "3",
            "probe": "4",
        },
        "generated_at": datetime.now(UTC),
    }
    with pytest.raises(ValueError):
        Verdict(**base, tier=VerdictTier.V1, limitations="")  # type: ignore

    # V4 doesn't require limitations
    Verdict(**base, tier=VerdictTier.V4, limitations="")  # type: ignore
    # (Append these to your existing tests/unit/test_models.py)


def test_contract_before_after_accept_null(
    valid_candidate_dict: dict[str, object],
) -> None:
    from driftguard.models.core import ContractCandidate

    valid_candidate_dict["before"] = None
    valid_candidate_dict["after"] = None
    cand = ContractCandidate(**valid_candidate_dict)  # type: ignore
    assert cand.before is None
    assert cand.after is None


def test_make_contract_id_changes_when_EACH_input_changes() -> None:
    base_id = make_contract_id("v", "p", "v:p:k:n", "removal", "2024-01-01", "1")
    assert (
        make_contract_id("x", "p", "v:p:k:n", "removal", "2024-01-01", "1") != base_id
    )
    assert (
        make_contract_id("v", "x", "v:p:k:n", "removal", "2024-01-01", "1") != base_id
    )
    assert (
        make_contract_id("v", "p", "v:p:x:n", "removal", "2024-01-01", "1") != base_id
    )
    assert make_contract_id("v", "p", "v:p:k:n", "rename", "2024-01-01", "1") != base_id
    assert (
        make_contract_id("v", "p", "v:p:k:n", "removal", "2024-02-01", "1") != base_id
    )
    assert (
        make_contract_id("v", "p", "v:p:k:n", "removal", "2024-01-01", "2") != base_id
    )

    # Covers line 87-88 gap (IndexError inside split)
    assert "unknown" in make_contract_id(
        "v", "p", "badref", "removal", "2024-01-01", "1"
    )


def test_make_contract_id_is_stable_across_processes() -> None:
    code = """
import sys
from driftguard.models.core import make_contract_id
print(make_contract_id("v", "p", "v:p:k:n", "removal", "2024-01-01", "1"))
    """
    res1 = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    res2 = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert res1.stdout == res2.stdout


def test_lifecycle_transitions_tested_for_BOTH_Contract_and_Impact() -> None:
    assert can_transition("contract", "NEW", "EXTRACTED")
    assert not can_transition("contract", "NEW", "ACTIVE")
    assert can_transition("impact", "DETECTED", "TRIAGED")
    assert not can_transition("impact", "DETECTED", "VERIFYING")

    # Coverage gap for transitions.py line 36
    assert not can_transition("invalid_model", "x", "y")


def test_UsageRecord_confidence_out_of_range_rejected() -> None:
    from driftguard.models.core import UsageRecord

    base = {
        "repo": "x",
        "commit_sha": "y",
        "file": "z",
        "line": 1,
        "symbol": "a",
        "vendor": "v",
        "surface_ref": "v:p:k:n",
        "kind": "call",
        "detector": "rule",
    }
    with pytest.raises(ValueError):
        UsageRecord(**base, confidence=1.5)  # type: ignore
    with pytest.raises(ValueError):
        UsageRecord(**base, confidence=-0.1)  # type: ignore


def test_usage_record_surface_ref_validation() -> None:
    from driftguard.models.core import UsageRecord

    valid = {
        "repo": "r",
        "commit_sha": "c",
        "file": "f",
        "line": 1,
        "symbol": "s",
        "vendor": "acme",
        "surface_ref": "acme:models:model:acme-pro-2025-01",
        "kind": "call",
        "confidence": 1.0,
        "detector": "rule",
    }
    UsageRecord(**valid)  # Should pass

    invalid = valid.copy()
    invalid["surface_ref"] = "model:acme-pro-2025-01"
    with pytest.raises(ValueError):
        UsageRecord(**invalid)  # type: ignore


def test_support_types_reject_unknown_fields() -> None:
    from driftguard.models.support import Workspace

    with pytest.raises(ValueError):
        Workspace(path="/tmp", unknown_field="bad")  # type: ignore
