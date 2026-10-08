import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import feedparser  # type: ignore
from selectolax.lexbor import LexborHTMLParser

from driftguard.models.support import Entry, RawDocument, Source


class EntrySplitter(Protocol):
    def split(self, doc: RawDocument) -> list[Entry]: ...


@dataclass
class DiffResult:
    new: list[Entry]
    changed: list[Entry]
    unchanged: list[Entry]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_date(date_str: str) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return None


class HtmlSplitter:
    def __init__(self, source: Source):
        self.source = source
        self.selector = self.source.parser_hints.get(
            "entry_selector", '[id^="entry-"], article'
        )
        self.title_selector = self.source.parser_hints.get(
            "title_selector", "h1, h2, h3, h4"
        )

    def split(self, doc: RawDocument) -> list[Entry]:
        tree = LexborHTMLParser(doc.text)
        # Use a dict to deduplicate nodes matched multiple times by comma selectors
        entries_dict = {}

        for node in tree.css(self.selector):
            norm_text = normalize_text(node.text(separator=" "))
            if not norm_text:
                continue

            node_id = node.attributes.get("id")
            c_hash = compute_hash(norm_text)
            entry_id = (
                f"{self.source.id}#{node_id}"
                if node_id
                else f"{self.source.id}#{c_hash[:12]}"
            )

            title = None
            title_node = node.css_first(self.title_selector)
            if title_node:
                title = normalize_text(title_node.text(separator=" "))

            pub_date = None
            time_node = node.css_first("time[datetime]")
            if time_node and time_node.attributes.get("datetime"):
                pub_date = parse_date(time_node.attributes.get("datetime") or "")
            if not pub_date and node.attributes.get("data-date"):
                pub_date = parse_date(node.attributes.get("data-date") or "")
            if not pub_date:
                match = re.search(r"Published:\s*(\d{4}-\d{2}-\d{2})", norm_text)
                if match:
                    pub_date = parse_date(match.group(1))

            entries_dict[entry_id] = Entry(
                id=entry_id,
                source_id=self.source.id,
                doc_url=doc.url,
                title=title,
                published_at=pub_date,
                text=norm_text,
                content_hash=c_hash,
            )

        return list(entries_dict.values())


class HtmlTableSplitter:
    def __init__(self, source: Source):
        self.source = source

    def split(self, doc: RawDocument) -> list[Entry]:
        tree = LexborHTMLParser(doc.text)
        entries = []
        table = tree.css_first("table")
        if not table:
            return []

        rows = table.css("tr")
        if len(rows) < 2:
            return []

        headers = [
            normalize_text(th.text(separator=" ")) for th in rows[0].css("th, td")
        ]

        for row in rows[1:]:
            cells = [normalize_text(td.text(separator=" ")) for td in row.css("td, th")]
            if not cells or not cells[0]:
                continue

            slug = re.sub(r"[^a-z0-9]+", "-", cells[0].lower()).strip("-")
            entry_id = f"{self.source.id}#row-{slug}"

            paired = [
                f"{headers[i] if i < len(headers) else f'col{i}'}: {cell}"
                for i, cell in enumerate(cells)
            ]
            norm_text = normalize_text(" | ".join(paired))
            c_hash = compute_hash(norm_text)

            entries.append(
                Entry(
                    id=entry_id,
                    source_id=self.source.id,
                    doc_url=doc.url,
                    title=None,
                    published_at=None,
                    text=norm_text,
                    content_hash=c_hash,
                )
            )
        return entries


class RssSplitter:
    def __init__(self, source: Source):
        self.source = source

    def split(self, doc: RawDocument) -> list[Entry]:
        feed = feedparser.parse(doc.text)
        entries = []
        for item in feed.entries:
            title = getattr(item, "title", "")
            desc_raw = getattr(item, "description", getattr(item, "summary", ""))
            desc = LexborHTMLParser(desc_raw).text(separator=" ") if desc_raw else ""

            norm_text = normalize_text(f"{title}. {desc}")
            c_hash = compute_hash(norm_text)

            guid = getattr(item, "id", getattr(item, "guid", None))
            link = getattr(item, "link", None)

            pub_parsed = getattr(item, "published_parsed", None)
            pub_date = None
            if pub_parsed:
                try:
                    pub_date = date(
                        pub_parsed.tm_year,
                        pub_parsed.tm_mon,
                        pub_parsed.tm_mday,
                    )
                except ValueError:
                    pass

            raw_date_str = getattr(item, "published", getattr(item, "updated", ""))
            eid = guid or link or compute_hash(f"{title}{raw_date_str}")

            entries.append(
                Entry(
                    id=eid,
                    source_id=self.source.id,
                    doc_url=doc.url,
                    title=title if title else None,
                    published_at=pub_date,
                    text=norm_text,
                    content_hash=c_hash,
                )
            )
        return entries


class OpenApiSplitter:
    def __init__(self, source: Source):
        pass

    def split(self, doc: RawDocument) -> list[Entry]:
        raise NotImplementedError("handled by deterministic extractor")


def make_splitter(source: Source) -> EntrySplitter:
    if source.type == "html":
        return HtmlSplitter(source)
    if source.type == "html_table":
        return HtmlTableSplitter(source)
    if source.type == "rss":
        return RssSplitter(source)
    if source.type == "openapi":
        return OpenApiSplitter(source)
    raise ValueError(f"Unsupported source type: {source.type}")


def diff_entries(known: dict[str, str], entries: list[Entry]) -> DiffResult:
    new, changed, unchanged = [], [], []
    known_hashes = set(known.values())

    for e in entries:
        if e.content_hash in known_hashes:
            unchanged.append(e)
        elif e.id in known:
            changed.append(e)
        else:
            new.append(e)

    return DiffResult(new=new, changed=changed, unchanged=unchanged)
