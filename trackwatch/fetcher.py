"""Responsible fetching of publicly available source pages.

Stdlib only: urllib.request for HTTP, urllib.robotparser for robots.txt.
No Selenium/Playwright, no login automation, no CAPTCHA handling, no proxy
rotation. If a source can't be fetched the normal way a browser would fetch
a public page, TrackWatch does not fetch it.
"""

import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_USER_AGENT = "GulfSouthDrags-TrackWatch/0.1 (+https://gulfsouthdrags.com)"
DEFAULT_TIMEOUT = 15

_robots_cache = {}


@dataclass
class FetchResult:
    ok: bool
    url: str
    final_url: str = ""
    status: int = 0
    body: str = ""
    etag: str = ""
    last_modified: str = ""
    not_modified: bool = False
    error: str = ""
    retry_after: str = ""
    blocked_by_robots: bool = False


def _robots_allows(url, user_agent):
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(origin + "/robots.txt")
        try:
            rp.read()
        except Exception:
            # No readable robots.txt (404, timeout, etc.) — treat as no
            # restriction, same as any normal browser would.
            rp = None
        _robots_cache[origin] = rp
    if rp is None:
        return True
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True


def fetch(url, *, user_agent=DEFAULT_USER_AGENT, timeout=DEFAULT_TIMEOUT,
          etag="", last_modified=""):
    """Fetch one URL. Returns a FetchResult; never raises for ordinary
    network/HTTP failures — those come back as ok=False with .error set."""
    if not _robots_allows(url, user_agent):
        return FetchResult(ok=False, url=url, blocked_by_robots=True,
                            error="disallowed by robots.txt")

    headers = {"User-Agent": user_agent, "Accept": "text/html,*/*;q=0.8"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body_bytes = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            body = body_bytes.decode(charset, errors="replace")
            return FetchResult(
                ok=True, url=url, final_url=resp.geturl(), status=status,
                body=body, etag=resp.headers.get("ETag", ""),
                last_modified=resp.headers.get("Last-Modified", ""),
            )
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return FetchResult(ok=True, url=url, final_url=url, status=304,
                                not_modified=True)
        retry_after = e.headers.get("Retry-After", "") if e.headers else ""
        return FetchResult(ok=False, url=url, status=e.code,
                            error=f"HTTP {e.code}", retry_after=retry_after)
    except urllib.error.URLError as e:
        return FetchResult(ok=False, url=url, error=f"unreachable: {e.reason}")
    except TimeoutError:
        return FetchResult(ok=False, url=url, error="timeout")
    except Exception as e:  # last resort — one bad source can't crash a sweep
        return FetchResult(ok=False, url=url, error=f"unexpected error: {e}")


def polite_sleep(seconds=1.0):
    """A small fixed pause between fetches. We're checking dragstrip
    schedules, not scraping at speed — there is no reason to hammer a
    track's small hosting plan."""
    time.sleep(seconds)
