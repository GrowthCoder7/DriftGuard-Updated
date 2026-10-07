from pathlib import Path

import yaml

from driftguard.models.support import Politeness, Source


def load_registry(path: Path) -> list[Source]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "vendors" not in data:
        return []

    sources: list[Source] = []
    allowed_source_keys = {"url", "type", "cadence", "parser_hints", "politeness"}

    for vendor, vendor_data in data["vendors"].items():
        vendor_sources = vendor_data.get("sources", [])
        type_counts: dict[str, int] = {}

        for src_data in vendor_sources:
            for k in src_data:
                if k not in allowed_source_keys:
                    raise ValueError(
                        f"Unknown key {k} in {path.name} for vendor {vendor}"
                    )

            stype = src_data.get("type")
            if stype not in {"html", "html_table", "rss", "openapi"}:
                raise ValueError(f"Invalid type {stype} for vendor {vendor}")

            url = src_data.get("url")
            if not url:
                raise ValueError(f"Missing url for vendor {vendor}")

            scheme = url.split("://")[0]
            if scheme not in {"http", "https", "file"}:
                raise ValueError(
                    f"Bad scheme {scheme} in {path.name} for vendor {vendor}"
                )

            politeness_data = src_data.get("politeness", {})
            if "min_interval_seconds" not in politeness_data:
                raise ValueError(
                    f"Missing politeness.min_interval_seconds for vendor {vendor}"
                )
            if "user_agent" not in politeness_data:
                raise ValueError(f"Missing politeness.user_agent for vendor {vendor}")

            count = type_counts.get(stype, 0) + 1
            type_counts[stype] = count

            suffix = f"-{count}" if count > 1 else ""
            source_id = f"{vendor}-{stype}{suffix}"

            sources.append(
                Source(
                    id=source_id,
                    vendor=vendor,
                    type=stype,  # type: ignore
                    url=url,
                    cadence=src_data.get("cadence", ""),
                    parser_hints=src_data.get("parser_hints", {}),
                    politeness=Politeness(
                        min_interval_seconds=float(
                            politeness_data["min_interval_seconds"]
                        ),
                        user_agent=str(politeness_data["user_agent"]),
                    ),
                )
            )

    return sources
