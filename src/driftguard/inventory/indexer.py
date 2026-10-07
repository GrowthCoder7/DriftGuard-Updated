import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Set

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from driftguard.models.core import UsageRecord

logger = logging.getLogger(__name__)

class PythonIndexer:
    def __init__(self, alias_map: dict[str, dict[str, str]]):
        self.alias_map = alias_map
        
        lang = tspython.language()
        if not isinstance(lang, Language):
            lang = Language(lang)

        try:
            self.parser = Parser(lang)
        except Exception:
            self.parser = Parser()
            self.parser.language = lang

    def _get_head_sha(self, snapshot: Path) -> str:
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(snapshot), encoding="utf-8", stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            return "unknown"

    def _create_record(self, oid: str, rel_path: str, line_no: int, text: str, snapshot: Path, head_sha: str, kind: str, detector: str) -> UsageRecord:
        parts = oid.split(":")
        vendor = parts[0] if len(parts) > 0 else "unknown"
        surface_type = parts[2] if len(parts) > 2 else "unknown"
        name = parts[3] if len(parts) > 3 else "unknown"
        
        return UsageRecord(
            repo=snapshot.name,
            commit_sha=head_sha,
            file=rel_path,
            line=line_no,
            symbol=text,
            vendor=vendor,
            surface_ref=f"{surface_type}:{name}",
            kind=kind,
            confidence=1.0,
            detector=detector
        )

    def scan(self, snapshot: Path, since: Optional[str] = None) -> List[UsageRecord]:
        changed_files: Optional[Set[str]] = None
        if since:
            try:
                out = subprocess.check_output(
                    ["git", "-c", "core.autocrlf=false", "diff", "--name-only", since],
                    cwd=str(snapshot), encoding="utf-8"
                )
                changed_files = {line.strip() for line in out.splitlines() if line.strip()}
            except subprocess.CalledProcessError:
                logger.warning("Git diff failed, falling back to full scan")

        head_sha = self._get_head_sha(snapshot)
        records: List[UsageRecord] = []
        skip_dirs = {".git", ".venv", "node_modules", "__pycache__"}

        for root, dirs, files in os.walk(snapshot):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                filepath = Path(root) / file
                rel_path = filepath.relative_to(snapshot).as_posix()

                if changed_files is not None and rel_path not in changed_files:
                    continue

                if filepath.stat().st_size > 1024 * 1024:
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    continue

                content = content.replace("\r\n", "\n")

                if file.endswith(".py"):
                    records.extend(self._parse_python(content, rel_path, snapshot, head_sha))
                
                records.extend(self._parse_config(content, rel_path, filepath.name, snapshot, head_sha))

        return records

    def _parse_python(self, content: str, rel_path: str, snapshot: Path, head_sha: str) -> List[UsageRecord]:
        records = []
        tree = self.parser.parse(bytes(content, "utf8"))
        
        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)

        for node in walk(tree.root_node):
            line_no = node.start_point[0] + 1
            
            if node.type == "keyword_argument":
                name_node = node.child_by_field_name("name")
                if name_node:
                    text = name_node.text.decode("utf8") if isinstance(name_node.text, bytes) else name_node.text
                    if oid := self.alias_map["kwargs"].get(text):
                        records.append(self._create_record(oid, rel_path, line_no, text, snapshot, head_sha, "call", "tree-sitter"))
            
            elif node.type == "string_content":
                text = node.text.decode("utf8") if isinstance(node.text, bytes) else node.text
                if text in self.alias_map["models"]:
                    oid = self.alias_map["models"][text]
                    records.append(self._create_record(oid, rel_path, line_no, text, snapshot, head_sha, "model_string", "tree-sitter"))
                else:
                    for host, oid in self.alias_map["hostnames"].items():
                        if host in text:
                            records.append(self._create_record(oid, rel_path, line_no, host, snapshot, head_sha, "url", "tree-sitter"))
            
            elif node.type == "import_from_statement":
                mod_node = node.child_by_field_name("module_name")
                if mod_node:
                    text = mod_node.text.decode("utf8") if isinstance(mod_node.text, bytes) else mod_node.text
                    if oid := self.alias_map["imports"].get(text):
                        records.append(self._create_record(oid, rel_path, line_no, text, snapshot, head_sha, "import", "tree-sitter"))

            elif node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        text = child.text.decode("utf8") if isinstance(child.text, bytes) else child.text
                        if oid := self.alias_map["imports"].get(text):
                            records.append(self._create_record(oid, rel_path, line_no, text, snapshot, head_sha, "import", "tree-sitter"))

        return records

    def _parse_config(self, content: str, rel_path: str, filename: str, snapshot: Path, head_sha: str) -> List[UsageRecord]:
        records = []
        lines = content.split("\n")
        
        is_manifest = filename in ("requirements.txt", "pyproject.toml")
        is_config = filename.endswith((".yaml", ".yml", ".json", ".toml", ".env"))

        for i, line in enumerate(lines):
            line_no = i + 1
            if is_manifest:
                for dep, oid in self.alias_map["manifest_deps"].items():
                    if dep in line:
                        records.append(self._create_record(oid, rel_path, line_no, dep, snapshot, head_sha, "manifest", "regex"))
            if is_config:
                for mod, oid in self.alias_map["models"].items():
                    if mod in line:
                        records.append(self._create_record(oid, rel_path, line_no, mod, snapshot, head_sha, "config", "regex"))
                for host, oid in self.alias_map["hostnames"].items():
                    if host in line:
                        records.append(self._create_record(oid, rel_path, line_no, host, snapshot, head_sha, "url", "regex"))

        return records