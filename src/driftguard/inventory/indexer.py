import logging
import os
import subprocess
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from driftguard.models.core import UsageRecord
from driftguard.models.support import AliasMap, RepoSnapshot

logger = logging.getLogger(__name__)


class PythonIndexer:
    def __init__(self, alias_map: AliasMap):
        self.alias_map = alias_map
        self.lookups = self._build_lookups(alias_map)

        lang = tspython.language()
        if not isinstance(lang, Language):
            lang = Language(lang)

        try:
            self.parser = Parser(lang)
        except Exception:
            self.parser = Parser()
            self.parser.language = lang

    def _build_lookups(self, alias_map: AliasMap) -> dict[str, dict[str, str]]:
        lookups: dict[str, dict[str, str]] = {
            "models": {},
            "kwargs": {},
            "imports": {},
            "hostnames": {},
            "manifest_deps": {},
            "module_to_vendor": {},
        }
        for entry in alias_map.entries:
            oid = entry.ontology_id
            vendor = oid.split(":")[0] if ":" in oid else "unknown"
            for m in entry.model_aliases:
                lookups["models"][m] = oid
            for s in entry.sdk_symbols:
                parts = s.split(".")
                lookups["kwargs"][parts[-1]] = oid
                if len(parts) > 1:
                    mod = parts[0]
                    lookups["imports"][mod] = oid
                    lookups["module_to_vendor"][mod] = vendor
            for h in entry.hostnames:
                lookups["hostnames"][h] = oid
            for md in entry.manifest_deps:
                lookups["manifest_deps"][md] = oid
        return lookups

    def _get_head_sha(self, path: Path) -> str:
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(path),
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return "unknown"

    def _create_record(
        self,
        oid: str,
        rel_path: str,
        line_no: int,
        text: str,
        snapshot: RepoSnapshot,
        head_sha: str,
        kind: str,
        detector: str,
        confidence: float = 1.0,
    ) -> UsageRecord:
        vendor = oid.split(":")[0] if ":" in oid else "unknown"
        return UsageRecord(
            repo=snapshot.repo,
            commit_sha=head_sha,
            file=rel_path,
            line=line_no,
            symbol=text,
            vendor=vendor,
            surface_ref=oid,
            kind=kind,
            confidence=confidence,
            detector=detector,
        )

    def scan(self, snapshot: RepoSnapshot, since: str | None) -> list[UsageRecord]:
        changed_files: set[str] | None = None
        repo_path = Path(snapshot.path)
        if since:
            try:
                out = subprocess.check_output(
                    ["git", "-c", "core.autocrlf=false", "diff", "--name-only", since],
                    cwd=str(repo_path),
                    encoding="utf-8",
                )
                changed_files = {
                    line.strip() for line in out.splitlines() if line.strip()
                }
            except subprocess.CalledProcessError:
                logger.warning("Git diff failed, falling back to full scan")

        head_sha = snapshot.sha or self._get_head_sha(repo_path)
        records: list[UsageRecord] = []
        skip_dirs = {".git", ".venv", "node_modules", "__pycache__"}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                filepath = Path(root) / file
                rel_path = filepath.relative_to(repo_path).as_posix()

                if changed_files is not None and rel_path not in changed_files:
                    continue

                if filepath.stat().st_size > 1024 * 1024:
                    continue

                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    continue

                content = content.replace("\r\n", "\n")

                if file.endswith(".py"):
                    records.extend(
                        self._parse_python(content, rel_path, snapshot, head_sha)
                    )

                records.extend(
                    self._parse_config(
                        content, rel_path, filepath.name, snapshot, head_sha
                    )
                )

        return records

    def _parse_python(
        self, content: str, rel_path: str, snapshot: RepoSnapshot, head_sha: str
    ) -> list[UsageRecord]:
        records = []
        tree = self.parser.parse(bytes(content, "utf8"))

        imported_vendors = set()
        raw_captures = []

        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)

        for node in walk(tree.root_node):
            if node.type in ("import_from_statement", "import_statement"):
                for child in node.children:
                    if child.type == "dotted_name":
                        text = (
                            child.text.decode("utf8")
                            if isinstance(child.text, bytes)
                            else child.text
                        )
                        mod_base = text.split(".")[0]
                        if mod_base in self.lookups["module_to_vendor"]:
                            imported_vendors.add(
                                self.lookups["module_to_vendor"][mod_base]
                            )

            if node.type == "keyword_argument":
                name_node = node.child_by_field_name("name")
                if name_node:
                    text = (
                        name_node.text.decode("utf8")
                        if isinstance(name_node.text, bytes)
                        else name_node.text
                    )
                    raw_captures.append((name_node, "kw_arg", text))
            elif node.type == "string_content":
                text = (
                    node.text.decode("utf8")
                    if isinstance(node.text, bytes)
                    else node.text
                )
                raw_captures.append((node, "str_content", text))
            elif (
                node.type == "dotted_name"
                and node.parent
                and node.parent.type
                in (
                    "import_from_statement",
                    "import_statement",
                )
            ):
                text = (
                    node.text.decode("utf8")
                    if isinstance(node.text, bytes)
                    else node.text
                )
                raw_captures.append((node, "import_mod", text))

        for node, name, text in raw_captures:
            line_no = node.start_point[0] + 1

            if name == "kw_arg":
                if oid := self.lookups["kwargs"].get(text):
                    vendor = oid.split(":")[0] if ":" in oid else "unknown"
                    confidence = 1.0 if vendor in imported_vendors else 0.5
                    records.append(
                        self._create_record(
                            oid,
                            rel_path,
                            line_no,
                            text,
                            snapshot,
                            head_sha,
                            "call",
                            "tree-sitter",
                            confidence,
                        )
                    )

            elif name == "str_content":
                if text in self.lookups["models"]:
                    oid = self.lookups["models"][text]
                    records.append(
                        self._create_record(
                            oid,
                            rel_path,
                            line_no,
                            text,
                            snapshot,
                            head_sha,
                            "model_string",
                            "tree-sitter",
                            1.0,
                        )
                    )
                else:
                    for host, oid in self.lookups["hostnames"].items():
                        if host in text:
                            records.append(
                                self._create_record(
                                    oid,
                                    rel_path,
                                    line_no,
                                    host,
                                    snapshot,
                                    head_sha,
                                    "url",
                                    "tree-sitter",
                                    1.0,
                                )
                            )

            elif name == "import_mod":
                mod_base = text.split(".")[0]
                if oid := self.lookups["imports"].get(mod_base):
                    records.append(
                        self._create_record(
                            oid,
                            rel_path,
                            line_no,
                            text,
                            snapshot,
                            head_sha,
                            "import",
                            "tree-sitter",
                            1.0,
                        )
                    )

        return records

    def _parse_config(
        self,
        content: str,
        rel_path: str,
        filename: str,
        snapshot: RepoSnapshot,
        head_sha: str,
    ) -> list[UsageRecord]:
        records = []
        lines = content.split("\n")

        is_manifest = filename in ("requirements.txt", "pyproject.toml")
        is_config = filename.endswith((".yaml", ".yml", ".json", ".toml", ".env"))

        for i, line in enumerate(lines):
            line_no = i + 1
            if is_manifest:
                for dep, oid in self.lookups["manifest_deps"].items():
                    if dep in line:
                        records.append(
                            self._create_record(
                                oid,
                                rel_path,
                                line_no,
                                dep,
                                snapshot,
                                head_sha,
                                "manifest",
                                "regex",
                            )
                        )
            if is_config:
                for mod, oid in self.lookups["models"].items():
                    if mod in line:
                        records.append(
                            self._create_record(
                                oid,
                                rel_path,
                                line_no,
                                mod,
                                snapshot,
                                head_sha,
                                "config",
                                "regex",
                            )
                        )
                for host, oid in self.lookups["hostnames"].items():
                    if host in line:
                        records.append(
                            self._create_record(
                                oid,
                                rel_path,
                                line_no,
                                host,
                                snapshot,
                                head_sha,
                                "url",
                                "regex",
                            )
                        )

        return records
