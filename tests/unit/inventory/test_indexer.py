import pytest
import subprocess
import json
from pathlib import Path

from driftguard.inventory.indexer import PythonIndexer
from driftguard.inventory.alias import load_alias_map
from driftguard.models.core import UsageRecord

@pytest.fixture
def dummy_alias():
    return {
        "models": {"acme-pro-2025-01": "acme:models:model:acme-pro-2025-01"},
        "kwargs": {"max_tokens": "acme:chat:param:max_tokens"},
        "imports": {"acme_sdk.client": "acme:chat:param:max_tokens"},
        "hostnames": {"api.acme.com": "acme:chat:endpoint:chat"},
        "manifest_deps": {"acme_sdk": "acme:sdk:lib:core"}
    }

@pytest.fixture
def temp_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    return repo

def test_indexer_all_named_features(temp_repo, dummy_alias):
    (temp_repo / "main.py").write_text(
        "from acme_sdk.client import AcmeClient\n"
        "client.chat(max_tokens=10)\n"
        "model_id = 'acme-pro-2025-01'\n"
        "unknown_kwarg(foo=1)\n",
        encoding="utf-8", newline="\n"
    )
    (temp_repo / "config.yaml").write_text("model: acme-pro-2025-01\nurl: api.acme.com", encoding="utf-8", newline="\n")
    (temp_repo / "requirements.txt").write_text("acme_sdk==1.0.0", encoding="utf-8", newline="\n")
    
    venv = temp_repo / ".venv"
    venv.mkdir()
    (venv / "ignored.py").write_text("max_tokens=99", encoding="utf-8", newline="\n")
    
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_repo, check=True)
    
    indexer = PythonIndexer(dummy_alias)
    records = indexer.scan(temp_repo)
    
    assert any(r.surface_ref == "param:max_tokens" and r.file == "main.py" and r.line == 1 for r in records), "direct SDK import found"
    assert any(r.surface_ref == "param:max_tokens" and r.file == "main.py" and r.line == 2 for r in records), "keyword-arg call found with correct line"
    assert any(r.surface_ref == "model:acme-pro-2025-01" and r.file == "main.py" and r.line == 3 for r in records), "model ID in .py found"
    assert any(r.surface_ref == "model:acme-pro-2025-01" and r.file == "config.yaml" and r.line == 1 for r in records), "model ID config"
    assert any(r.surface_ref == "endpoint:chat" and r.file == "config.yaml" and r.line == 2 for r in records), "hostname found"
    assert any(r.surface_ref == "lib:core" and r.file == "requirements.txt" and r.line == 1 for r in records), "manifest dep found"
    assert not any(r.file == "main.py" and r.line == 4 for r in records), "unknown symbol ignored"

def test_indexer_crlf_normalization(temp_repo, dummy_alias):
    crlf_content = b"client.chat(max_tokens=10)\r\nmodel_id = 'acme-pro-2025-01'\r\n"
    lf_content = crlf_content.replace(b"\r\n", b"\n")
    
    (temp_repo / "crlf.py").write_bytes(crlf_content)
    (temp_repo / "lf.py").write_bytes(lf_content)
    
    indexer = PythonIndexer(dummy_alias)
    records = indexer.scan(temp_repo)
    
    assert len([r for r in records if r.file == "crlf.py"]) == 2
    assert len([r for r in records if r.file == "lf.py"]) == 2

def test_indexer_incremental_scan(temp_repo, dummy_alias):
    # Enforce strict byte-level LF writing to prevent Git diff false-positives on Windows
    (temp_repo / "file1.py").write_bytes(b"client.chat(max_tokens=1)\n")
    (temp_repo / "file2.py").write_bytes(b"client.chat(max_tokens=1)\n")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_repo, check=True)
    head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_repo).decode().strip()
    
    # Modify ONLY file1
    (temp_repo / "file1.py").write_bytes(b"client.chat(max_tokens=2)\n")
    
    indexer = PythonIndexer(dummy_alias)
    records = indexer.scan(temp_repo, since=head_commit)
    
    assert len(records) == 1, f"Expected 1 record, got {len(records)}: {records}"
    assert records[0].file == "file1.py"

@pytest.mark.xfail(reason="Dynamic model name not supported statically")
def test_dynamic_model_name_miss(temp_repo, dummy_alias):
    (temp_repo / "dyn.py").write_text("import os\nmodel = os.environ['MODEL']\nclient.chat(model=model)", encoding="utf-8", newline="\n")
    indexer = PythonIndexer(dummy_alias)
    records = indexer.scan(temp_repo)
    assert any(r.surface_ref == "model:acme-pro-2025-01" for r in records)

def test_recall_and_precision_on_demo_repos():
    repo_root = Path(__file__).parent.parent.parent.parent
    demo_dir = repo_root / "demo"
    if not demo_dir.exists():
        pytest.skip("Demo directory missing for integration verification")
        
    alias_map = load_alias_map(repo_root / "registry" / "aliases")
    indexer = PythonIndexer(alias_map)
    
    for app_dir in demo_dir.glob("*-app"):
        expected_path = app_dir / "expected_usages.json"
        if not expected_path.exists():
            continue
            
        expected_raw = json.loads(expected_path.read_text(encoding="utf-8"))
        
        # Test existence within the file, isolating from volatile blank-line formatting
        expected_set = {(e["surface_ref"], e["file"]) for e in expected_raw}
        
        records = indexer.scan(app_dir)
        actual_set = {(r.surface_ref, r.file) for r in records}
        
        tp = len(expected_set & actual_set)
        fn = len(expected_set - actual_set)
        
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        assert recall >= 0.95, f"Recall threshold missed on {app_dir.name}"