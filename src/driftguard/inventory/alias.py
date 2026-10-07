from pathlib import Path

import yaml


def load_alias_map(registry_path: Path) -> dict[str, dict[str, str]]:
    """Loads YAML aliases into O(1) lookup dictionaries for the indexer."""
    lookups: dict[str, dict[str, str]] = {
        "models": {},
        "kwargs": {},
        "imports": {},
        "hostnames": {},
        "manifest_deps": {},
    }

    if not registry_path.exists():
        return lookups

    for yaml_file in registry_path.glob("**/*.yaml"):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            for alias in data.get("aliases", []):
                oid = alias["ontology_id"]

                for m in alias.get("model_aliases", []):
                    lookups["models"][m] = oid

                for s in alias.get("sdk_symbols", []):
                    parts = s.split(".")
                    lookups["kwargs"][parts[-1]] = oid
                    if len(parts) > 1:
                        # Extract module import paths (e.g., acme_sdk.client)
                        lookups["imports"][".".join(parts[:-1])] = oid

                for h in alias.get("hostnames", []):
                    lookups["hostnames"][h] = oid

                for md in alias.get("manifest_deps", []):
                    lookups["manifest_deps"][md] = oid

    return lookups
