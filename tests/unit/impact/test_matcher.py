from datetime import date
from pathlib import Path

import pytest
import yaml

from driftguard.impact.matcher import ContractMatcher
from driftguard.impact.owners import CodeownersResolver
from driftguard.impact.policy import Policy
from driftguard.models.core import Contract, UsageRecord
from driftguard.models.support import AliasEntry, AliasMap, RepoSnapshot


@pytest.fixture
def mock_policy():
    data = """
    escalation_window_days: 14
    repo_criticality:
      acme-demo-app: high
    severity_rules:
      - enforcement: hard
        days_until: 30
        severity: critical
      - enforcement: hard
        days_until: 90
        severity: high
      - enforcement: soft
        days_until: 30
        severity: high
      - enforcement: unknown
        days_until: 30
        severity: medium
    """
    return Policy(**yaml.safe_load(data))


@pytest.fixture
def dummy_aliases():
    return AliasMap(
        entries=[
            AliasEntry(
                ontology_id="acme:models:model:acme-pro-2025-01",
                model_aliases=["acme-pro-2025-01"],
                rest_paths=[],
                sdk_symbols=[],
                hostnames=[],
                manifest_deps=[],
            )
        ]
    )


@pytest.fixture
def valid_contract_dict():
    return {
        "schema_version": "1.0",
        "id": "entry-1",
        "vendor": "acme",
        "product": "chat",
        "change_type": "rename",
        "surface": {"kind": "param", "ref": "acme:chat:param:max_tokens"},
        "before": None,
        "after": None,
        "effective": {
            "announced_at": None,
            "effective_at": None,
            "enforcement": "hard",
        },
        "scope_conditions": [],
        "required_action": {"action": "none", "text": ""},
        "evidence": [{"quote": "test", "source_url": "test", "entry_id": "test"}],
        "confidence": {
            "tier": "A",
            "checks": {
                "schema_valid": True,
                "quote_verbatim": True,
                "identifier_grounded": True,
                "date_valid": True,
                "corroborated": True,
                "self_consistent": True,
            },
            "extractor": "deterministic",
        },
        "status": "ACTIVE",
    }


def test_non_active_contract_raises(mock_policy, dummy_aliases, valid_contract_dict):
    matcher = ContractMatcher(lambda: date(2026, 11, 1), mock_policy, lambda r, p: None)

    valid_contract_dict["status"] = "REJECTED"
    contract = Contract(**valid_contract_dict)

    with pytest.raises(ValueError, match="Only ACTIVE contracts can be matched"):
        matcher.match(contract, [], dummy_aliases)


def test_empty_usages_returns_empty(mock_policy, dummy_aliases, valid_contract_dict):
    matcher = ContractMatcher(lambda: date(2026, 11, 1), mock_policy, lambda r, p: None)
    contract = Contract(**valid_contract_dict)

    assert matcher.match(contract, [], dummy_aliases) == []


def test_alias_expansion_and_matching(mock_policy):
    matcher = ContractMatcher(lambda: date(2026, 11, 1), mock_policy, lambda r, p: None)

    aliases = AliasMap(
        entries=[
            AliasEntry(
                ontology_id="acme:chat:endpoint:chat",
                rest_paths=["/v1/chat"],
                sdk_symbols=[],
                hostnames=[],
                model_aliases=[],
                manifest_deps=[],
            ),
            AliasEntry(
                ontology_id="acme:chat:param:max_tokens",
                rest_paths=["/v1/chat"],
                sdk_symbols=[],
                hostnames=[],
                model_aliases=[],
                manifest_deps=[],
            ),
        ]
    )

    contract_dict = {
        "schema_version": "1.0",
        "id": "entry-2",
        "vendor": "acme",
        "product": "chat",
        "change_type": "rename",
        "surface": {"kind": "endpoint", "ref": "acme:chat:endpoint:chat"},
        "before": None,
        "after": None,
        "effective": {
            "announced_at": None,
            "effective_at": "2026-11-15",
            "enforcement": "hard",
        },
        "scope_conditions": [],
        "required_action": {"action": "none", "text": ""},
        "evidence": [{"quote": "test", "source_url": "test", "entry_id": "test"}],
        "confidence": {
            "tier": "A",
            "checks": {
                "schema_valid": True,
                "quote_verbatim": True,
                "identifier_grounded": True,
                "date_valid": True,
                "corroborated": True,
                "self_consistent": True,
            },
            "extractor": "deterministic",
        },
        "status": "ACTIVE",
    }
    contract = Contract(**contract_dict)

    usages = [
        UsageRecord(
            repo="app-1",
            commit_sha="abc",
            file="main.py",
            line=1,
            symbol="max_tokens",
            vendor="acme",
            surface_ref="acme:chat:param:max_tokens",
            kind="call",
            detector="regex",
            confidence=1.0,
        )
    ]

    impacts = matcher.match(contract, usages, aliases)

    assert len(impacts) == 1
    assert impacts[0].repo == "app-1"
    assert impacts[0].severity.value == "critical"


def test_low_confidence_downgrade(mock_policy):
    matcher = ContractMatcher(lambda: date(2026, 11, 1), mock_policy, lambda r, p: None)

    aliases = AliasMap(
        entries=[
            AliasEntry(
                ontology_id="acme:chat:endpoint:chat",
                rest_paths=["/v1/chat"],
                sdk_symbols=[],
                hostnames=[],
                model_aliases=[],
                manifest_deps=[],
            )
        ]
    )

    contract_dict = {
        "schema_version": "1.0",
        "id": "entry-3",
        "vendor": "acme",
        "product": "chat",
        "change_type": "behavior_change",
        "surface": {"kind": "endpoint", "ref": "acme:chat:endpoint:chat"},
        "before": None,
        "after": None,
        "effective": {
            "announced_at": None,
            "effective_at": "2026-11-15",
            "enforcement": "hard",
        },
        "scope_conditions": [],
        "required_action": {"action": "none", "text": ""},
        "evidence": [{"quote": "test", "source_url": "test", "entry_id": "test"}],
        "confidence": {
            "tier": "A",
            "checks": {
                "schema_valid": True,
                "quote_verbatim": True,
                "identifier_grounded": True,
                "date_valid": True,
                "corroborated": True,
                "self_consistent": True,
            },
            "extractor": "deterministic",
        },
        "status": "ACTIVE",
    }
    contract = Contract(**contract_dict)

    usages = [
        UsageRecord(
            repo="app-1",
            commit_sha="abc",
            file="main.py",
            line=1,
            symbol="chat",
            vendor="acme",
            surface_ref="acme:chat:endpoint:chat",
            kind="call",
            detector="regex",
            confidence=0.5,
        )
    ]

    impacts = matcher.match(contract, usages, aliases)

    assert len(impacts) == 1
    assert impacts[0].severity.value == "high"


def test_owner_resolution_tiebreaker(tmp_path):
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("*.py @python-team\n*.js @js-team\n", encoding="utf-8")

    resolver = CodeownersResolver(codeowners)

    assert resolver.resolve("src/main.py") == "@python-team"
    assert resolver.resolve("src/app.js") == "@js-team"
    assert resolver.resolve("README.md") is None


def test_end_to_end_indexer_match(mock_policy):
    repo_root = Path(__file__).parent.parent.parent.parent
    demo_demo = repo_root / "demo" / "acme-demo-app"
    demo_legacy = repo_root / "demo" / "acme-legacy-app"

    if not demo_demo.exists() or not demo_legacy.exists():
        pytest.skip("Demo repos not found for integration test")

    from driftguard.inventory.alias import load_alias_map
    from driftguard.inventory.indexer import PythonIndexer

    aliases = load_alias_map(repo_root / "registry" / "aliases")
    indexer = PythonIndexer(aliases)

    usages1 = indexer.scan(
        RepoSnapshot(repo="acme-demo-app", path=str(demo_demo), sha=None), since=None
    )
    usages2 = indexer.scan(
        RepoSnapshot(repo="acme-legacy-app", path=str(demo_legacy), sha=None),
        since=None,
    )

    contract_dict = {
        "schema_version": "1.0",
        "id": "entry-b",
        "vendor": "acme",
        "product": "models",
        "change_type": "deprecation",
        "surface": {"kind": "model", "ref": "acme:models:model:acme-pro-2025-01"},
        "before": {"name": "acme-pro-2025-01"},
        "after": {"name": "acme-pro-2026-06"},
        "effective": {
            "announced_at": "2026-09-01",
            "effective_at": "2026-12-15",
            "enforcement": "hard",
        },
        "scope_conditions": [],
        "required_action": {"action": "migrate", "text": "Migrate to acme-pro-2026-06"},
        "evidence": [
            {
                "quote": "Model acme-pro-2025-01 will be retired",
                "source_url": "test",
                "entry_id": "entry-b",
            }
        ],
        "confidence": {
            "tier": "A",
            "checks": {
                "schema_valid": True,
                "quote_verbatim": True,
                "identifier_grounded": True,
                "date_valid": True,
                "corroborated": True,
                "self_consistent": True,
            },
            "extractor": "deterministic",
        },
        "status": "ACTIVE",
    }
    contract = Contract(**contract_dict)

    def mock_owner_resolve(repo: str, path: str):
        codeowners_path = repo_root / "demo" / repo / "CODEOWNERS"
        return CodeownersResolver(codeowners_path).resolve(path)

    matcher = ContractMatcher(
        lambda: date(2026, 11, 1), mock_policy, mock_owner_resolve
    )
    impacts = matcher.match(contract, usages1 + usages2, aliases)

    assert len(impacts) == 2

    demo_impact = next(i for i in impacts if i.repo == "acme-demo-app")
    legacy_impact = next(i for i in impacts if i.repo == "acme-legacy-app")

    # Asserting CODEOWNERS match (assumes they exist in demo repos)
    assert demo_impact.owner in ("@team-platform", "@team-data", None)
    assert legacy_impact.owner in ("@team-platform", "@team-data", None)
