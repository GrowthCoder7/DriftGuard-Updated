from pathlib import Path

import yaml

from driftguard.models.support import Source


def load_registry_config(path: Path) -> dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return {}

    allowed_keys = {"url", "politeness", "user_agent"}
    for key, val in data.items():
        for k in val:
            if k not in allowed_keys:
                raise ValueError(f"Unknown key {k} in {path.name} for {key}")
        if "url" not in val:
            raise ValueError(f"Missing url in {path.name} for {key}")
        if "politeness" not in val or "min_interval_seconds" not in val["politeness"]:
            raise ValueError(
                f"Missing politeness.min_interval_seconds in {path.name} for {key}"
            )
        if "user_agent" not in val:
            raise ValueError(f"Missing user_agent in {path.name} for {key}")

        scheme = val["url"].split("://")[0]
        if scheme not in {"http", "https", "file"}:
            raise ValueError(f"Bad scheme {scheme} in {path.name} for {key}")

    return data


def load_registry(path: Path) -> list[Source]:
    config = load_registry_config(path)
    return [Source(id=k) for k in config]
