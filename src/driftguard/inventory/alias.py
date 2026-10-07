from pathlib import Path

import yaml

from driftguard.models.support import AliasEntry, AliasMap


def load_alias_map(registry_path: Path) -> AliasMap:
    """Loads YAML aliases strictly into an AliasMap."""
    entries = []
    if not registry_path.exists():
        return AliasMap(entries=entries)

    for yaml_file in registry_path.glob("**/*.yaml"):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            for alias_data in data.get("aliases", []):
                entries.append(
                    AliasEntry(
                        ontology_id=alias_data["ontology_id"],
                        sdk_symbols=alias_data.get("sdk_symbols", []),
                        rest_paths=alias_data.get("rest_paths", []),
                        hostnames=alias_data.get("hostnames", []),
                        model_aliases=alias_data.get("model_aliases", []),
                        manifest_deps=alias_data.get("manifest_deps", []),
                    )
                )

    return AliasMap(entries=entries)
