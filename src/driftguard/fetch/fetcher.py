import hashlib
import ipaddress
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser

import httpx

from driftguard.models.support import Checkpoint, RawDocument, Source
from driftguard.protocols import Fetcher


@dataclass
class FetchReport:
    successes: list[str]
    failures: dict[str, str]


class HttpFetcher(Fetcher):
    def __init__(
        self,
        clock,
        sleep,
        registry_config: dict[str, dict],
        allow_file=False,
        allow_local=False,
        client=None,
    ):
        self.clock = clock
        self.sleep = sleep
        self.registry = registry_config
        self.allow_file = allow_file
        self.allow_local = allow_local
        self.client = client or httpx.Client(timeout=10.0)
        self._last_fetch: dict[str, float] = {}

    def _is_private_host(self, host: str) -> bool:
        if host == "localhost":
            return True
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback
        except ValueError:
            return False

    def fetch(
        self, source: Source, checkpoint: Checkpoint | None = None
    ) -> tuple[list[RawDocument], Checkpoint]:
        config = self.registry.get(source.id)
        if not config:
            raise ValueError(f"Source {source.id} not found in registry")

        url = config["url"]
        user_agent = config["user_agent"]
        min_interval = config["politeness"]["min_interval_seconds"]
        parsed = urllib.parse.urlparse(url)

        if parsed.scheme == "file":
            if not self.allow_file:
                raise ValueError("file:// rejected when allow_file=False")

            # Reconstruct the file path correctly cross-platform
            path_str = urllib.request.url2pathname(parsed.netloc + parsed.path)
            path = Path(path_str)
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            if checkpoint and checkpoint.cursor:
                try:
                    cp_data = json.loads(checkpoint.cursor)
                    if cp_data.get("hash") == content_hash:
                        return [], checkpoint
                except json.JSONDecodeError:
                    pass

            doc = RawDocument(
                url=url,
                fetched_at=self.clock(),
                content_type="text/plain",
                text=text,
                content_hash=content_hash,
            )
            cp = Checkpoint(cursor=json.dumps({"hash": content_hash}))
            return [doc], cp

        if not self.allow_local and self._is_private_host(parsed.hostname or ""):
            raise ValueError("Private host rejected")

        # Robots.txt
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots_resp = self.client.get(
            robots_url, headers={"User-Agent": user_agent}, timeout=10.0
        )
        if robots_resp.status_code == 200:
            rp = RobotFileParser()
            rp.parse(robots_resp.text.splitlines())
            if not rp.can_fetch(user_agent, url):
                raise ValueError("robots disallow skips")

        # Politeness
        host = parsed.netloc
        last_t = self._last_fetch.get(host)
        if last_t:
            elapsed = (self.clock() - last_t).total_seconds()
            if elapsed < min_interval:
                self.sleep(min_interval - elapsed)

        # Conditional GET Headers
        headers = {"User-Agent": user_agent}
        if checkpoint and checkpoint.cursor:
            try:
                cp_data = json.loads(checkpoint.cursor)
                if cp_data.get("etag"):
                    headers["If-None-Match"] = cp_data["etag"]
                if cp_data.get("last_modified"):
                    headers["If-Modified-Since"] = cp_data["last_modified"]
            except json.JSONDecodeError:
                pass

        max_attempts = 3
        resp = None
        for attempt in range(max_attempts):
            self._last_fetch[host] = self.clock()
            resp = self.client.get(url, headers=headers, timeout=10.0)

            if resp.status_code in {429, 500, 502, 503, 504}:
                if attempt == max_attempts - 1:
                    raise ValueError(f"{resp.status_code} retries then fails closed")
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    if retry_after.isdigit():
                        delay = float(retry_after)
                    else:
                        dt = parsedate_to_datetime(retry_after)
                        delay = max(0.0, (dt - self.clock()).total_seconds())
                else:
                    delay = (2**attempt) + 0.1
                self.sleep(delay)
                continue
            break

        if resp.status_code == 304:
            return [], checkpoint or Checkpoint(cursor="{}")

        resp.raise_for_status()

        text = resp.text.replace("\r\n", "\n")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        etag = resp.headers.get("ETag")
        lm = resp.headers.get("Last-Modified")

        doc = RawDocument(
            url=url,
            fetched_at=self.clock(),
            content_type=resp.headers.get("Content-Type", "text/plain"),
            text=text,
            content_hash=content_hash,
            etag=etag,
            last_modified=lm,
        )
        cp = Checkpoint(
            cursor=json.dumps({"hash": content_hash, "etag": etag, "last_modified": lm})
        )
        return [doc], cp

    def fetch_all(
        self, sources: list[Source], checkpoints: dict[str, Checkpoint]
    ) -> FetchReport:
        successes = []
        failures = {}
        for source in sources:
            try:
                self.fetch(source, checkpoints.get(source.id))
                successes.append(source.id)
            except Exception as e:  # noqa: BLE001
                failures[source.id] = str(e)
        return FetchReport(successes=successes, failures=failures)
