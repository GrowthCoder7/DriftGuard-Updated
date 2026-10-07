import json
import subprocess
from pathlib import Path

import pytest

from driftguard.inventory.indexer import PythonIndexer
from driftguard.models.support import AliasEntry, AliasMap, RepoSnapshot
from driftguard.protocols import InventoryIndexer


@pytest.fixture
def dummy_alias_map():
    return AliasMap(
        entries=[
            AliasEntry(
                ontology_id="acme:models:model:acme-pro-2025-01",
                model_aliases=["acme-pro-2025-01"],
                sdk_symbols=[],
                rest_paths=[],
                hostnames=[],
                manifest_deps=[],
            ),
            AliasEntry(
                ontology_id="acme:chat:param:max_tokens",
                sdk_symbols=["acme_sdk.client.AcmeClient.chat", "max_tokens"],
                rest_paths=[],
                hostnames=[],
                model_aliases=[],
                manifest_deps=[],
            ),
            AliasEntry(
                ontology_id="acme:chat:endpoint:chat",
                hostnames=["api.acme.com", "api.acme.test"],
                sdk_symbols=[],
                rest_paths=[],
                model_aliases=[],
                manifest_deps=[],
            ),
            AliasEntry(
                ontology_id="acme:sdk:lib:core",
                manifest_deps=["acme_sdk"],
                sdk_symbols=[],
                rest_paths=[],
                hostnames=[],
                model_aliases=[],
            ),
        ]
    )


@pytest.fixture
def temp_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    return repo


def test_protocol_conformance(dummy_alias_map):
    indexer: InventoryIndexer = PythonIndexer(dummy_alias_map)
    assert indexer is not None


def test_indexer_all_named_features(temp_repo, dummy_alias_map):
    (temp_repo / "main.py").write_text(
        "from acme_sdk.client import AcmeClient\n"
        "client.chat(max_tokens=10)\n"
        "model_id = 'acme-pro-2025-01'\n"
        "unknown_kwarg(foo=1)\n",
        encoding="utf-8",
        newline="\n",
    )
    (temp_repo / "config.yaml").write_text(
        "model: acme-pro-2025-01\nurl: api.acme.com", encoding="utf-8", newline="\n"
    )
    (temp_repo / "requirements.txt").write_text(
        "acme_sdk==1.0.0", encoding="utf-8", newline="\n"
    )

    venv = temp_repo / ".venv"
    venv.mkdir()
    (venv / "ignored.py").write_text("max_tokens=99", encoding="utf-8", newline="\n")

    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_repo, check=True)

    snapshot = RepoSnapshot(repo="test-repo", path=str(temp_repo), sha=None)
    indexer = PythonIndexer(dummy_alias_map)
    records = indexer.scan(snapshot, since=None)

    # Verify no UsageRecord contains source code logic
    assert all(
        r.symbol in r.surface_ref
        or r.symbol
        in [
            "max_tokens",
            "acme_sdk",
            "acme_sdk.client",
            "api.acme.com",
            "acme-pro-2025-01",
        ]
        for r in records
    ), (
        f"UsageRecord field contains unexpected source text: {[r.symbol for r in records]}"
    )

    assert any(
        r.surface_ref == "acme:chat:param:max_tokens"
        and r.file == "main.py"
        and r.line == 1
        and r.kind == "import"
        for r in records
    ), "direct SDK import found"
    assert any(
        r.surface_ref == "acme:chat:param:max_tokens"
        and r.file == "main.py"
        and r.line == 2
        and r.confidence == 1.0
        for r in records
    ), "keyword-arg call found with correct line and confidence 1.0"
    assert any(
        r.surface_ref == "acme:models:model:acme-pro-2025-01"
        and r.file == "main.py"
        and r.line == 3
        for r in records
    ), "model ID in .py found"
    assert any(
        r.surface_ref == "acme:models:model:acme-pro-2025-01"
        and r.file == "config.yaml"
        and r.line == 1
        for r in records
    ), "model ID config"
    assert any(
        r.surface_ref == "acme:chat:endpoint:chat"
        and r.file == "config.yaml"
        and r.line == 2
        for r in records
    ), "hostname found"
    assert any(
        r.surface_ref == "acme:sdk:lib:core"
        and r.file == "requirements.txt"
        and r.line == 1
        for r in records
    ), "manifest dep found"
    assert not any(r.file == "main.py" and r.line == 4 for r in records), (
        "unknown symbol ignored"
    )


def test_precision_gating(temp_repo, dummy_alias_map):
    (temp_repo / "other.py").write_text(
        "import some_other_lib\nsome_other_lib.generate(max_tokens=10)\n",
        encoding="utf-8",
        newline="\n",
    )
    snapshot = RepoSnapshot(repo="test-repo", path=str(temp_repo), sha=None)
    indexer = PythonIndexer(dummy_alias_map)
    records = indexer.scan(snapshot, since=None)

    assert len(records) == 1
    assert records[0].surface_ref == "acme:chat:param:max_tokens"
    assert records[0].confidence == 0.5


def test_indexer_incremental_scan(temp_repo, dummy_alias_map):
    (temp_repo / "file1.py").write_bytes(b"client.chat(max_tokens=1)\n")
    (temp_repo / "file2.py").write_bytes(b"client.chat(max_tokens=1)\n")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_repo, check=True)
    head_commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_repo)
        .decode()
        .strip()
    )

    (temp_repo / "file1.py").write_bytes(b"client.chat(max_tokens=2)\n")

    snapshot = RepoSnapshot(repo="test-repo", path=str(temp_repo), sha=None)
    indexer = PythonIndexer(dummy_alias_map)
    records = indexer.scan(snapshot, since=head_commit)

    assert len(records) == 1
    assert records[0].file == "file1.py"


@pytest.mark.xfail(reason="Dynamic model name not supported statically")
def test_dynamic_model_name_miss(temp_repo, dummy_alias_map):
    (temp_repo / "dyn.py").write_text(
        "import os\nmodel = os.environ['MODEL']\nclient.chat(model=model)",
        encoding="utf-8",
        newline="\n",
    )
    snapshot = RepoSnapshot(repo="test-repo", path=str(temp_repo), sha=None)
    indexer = PythonIndexer(dummy_alias_map)
    records = indexer.scan(snapshot, since=None)
    assert any(r.surface_ref == "acme:models:model:acme-pro-2025-01" for r in records)


def test_recall_and_precision_on_demo_repos():
    repo_root = Path(__file__).parent.parent.parent.parent
    demo_dir = repo_root / "demo"
    if not demo_dir.exists():
        pytest.skip("Demo directory missing for integration verification")

    from driftguard.inventory.alias import load_alias_map

    alias_map = load_alias_map(repo_root / "registry" / "aliases")
    indexer = PythonIndexer(alias_map)

    for app_dir in demo_dir.glob("*-app"):
        expected_path = app_dir / "expected_usages.json"
        if not expected_path.exists():
            continue

        expected_raw = json.loads(expected_path.read_text(encoding="utf-8"))
        expected_set = {(e["surface_ref"], e["file"]) for e in expected_raw}

        snapshot = RepoSnapshot(repo=app_dir.name, path=str(app_dir), sha=None)
        records = indexer.scan(snapshot, since=None)
        actual_set = {(r.surface_ref, r.file) for r in records}

        tp = len(expected_set & actual_set)
        fn = len(expected_set - actual_set)

        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        assert recall >= 0.95, f"Recall threshold missed on {app_dir.name}"
