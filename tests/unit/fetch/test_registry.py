import pytest

from driftguard.fetch.registry import load_registry


def test_registry_valid_acme_file_parses(tmp_path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
vendors:
  acme:
    sources:
      - url: "https://acme.com/rss"
        type: "rss"
        cadence: "daily"
        parser_hints: {}
        politeness:
          min_interval_seconds: 5.0
          user_agent: "Bot"
      - url: "https://acme.com/rss2"
        type: "rss"
        politeness:
          min_interval_seconds: 5.0
          user_agent: "Bot"
""",
        encoding="utf-8",
    )
    sources = load_registry(reg)
    assert len(sources) == 2
    assert sources[0].id == "acme-rss"
    assert sources[1].id == "acme-rss-2"


def test_unknown_key_rejected(tmp_path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
vendors:
  acme:
    sources:
      - url: "https://acme.com/rss"
        type: "rss"
        fake_key: "bad"
        politeness: {"min_interval_seconds": 1, "user_agent": "x"}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown key fake_key"):
        load_registry(reg)


def test_missing_min_interval_rejected(tmp_path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
vendors:
  acme:
    sources:
      - url: "https://acme.com/rss"
        type: "rss"
        politeness: {"user_agent": "x"}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Missing politeness.min_interval_seconds"):
        load_registry(reg)


def test_bad_scheme_rejected(tmp_path):
    reg = tmp_path / "vendors.yaml"
    reg.write_text(
        """
vendors:
  acme:
    sources:
      - url: "ftp://acme.com"
        type: "rss"
        politeness: {"min_interval_seconds": 1, "user_agent": "x"}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Bad scheme ftp"):
        load_registry(reg)
