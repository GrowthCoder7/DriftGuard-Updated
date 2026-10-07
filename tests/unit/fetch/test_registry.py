from pathlib import Path

import pytest

from driftguard.fetch.registry import load_registry


def test_registry_valid_acme_file_parses(tmp_path: Path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
acme:
  url: "https://acme.com/api"
  politeness:
    min_interval_seconds: 5
  user_agent: "Bot"
""",
        encoding="utf-8",
    )
    sources = load_registry(reg)
    assert len(sources) == 1
    assert sources[0].id == "acme"


def test_unknown_key_rejected(tmp_path: Path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
acme:
  url: "https://acme.com/api"
  politeness:
    min_interval_seconds: 5
  user_agent: "Bot"
  fake_key: "bad"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown key fake_key"):
        load_registry(reg)


def test_missing_min_interval_rejected(tmp_path: Path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
acme:
  url: "https://acme.com/api"
  politeness: {}
  user_agent: "Bot"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min_interval_seconds"):
        load_registry(reg)


def test_bad_scheme_rejected(tmp_path: Path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
acme:
  url: "ftp://acme.com/api"
  politeness:
    min_interval_seconds: 5
  user_agent: "Bot"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Bad scheme"):
        load_registry(reg)
