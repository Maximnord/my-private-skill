#!/usr/bin/env python3
"""Shared HTTP helpers for the ai-visibility-method scripts.

Deliberately tiny: requests + a browser-shaped default UA, plus the real
product tokens of the AI crawlers so a fetch can be repeated "as a bot".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests

# Real product tokens as the vendors publish them. The exact string matters:
# WAF rules and robots.txt groups are matched against it.
AI_USER_AGENTS = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Perplexity-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "Google-Extended": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Applebot": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
    "Amazonbot": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
    "Bytespider": "Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)",
    "CCBot": "CCBot/2.0 (https://commoncrawl.org/faq/)",
}

# The bots whose access actually decides whether a brand can be cited in an AI
# answer today. Probing all of AI_USER_AGENTS is wasteful on most engagements.
CORE_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
             "PerplexityBot", "Google-Extended", "Bingbot"]

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,he;q=0.9,*;q=0.5",
    "Accept-Encoding": "gzip, deflate",
}

# Interstitials that return 200 but contain no content. Without this check a
# challenge page looks like a healthy fetch with a suspiciously short body.
CHALLENGE_MARKERS = (
    "just a moment", "checking your browser", "cf-browser-verification",
    "attention required! | cloudflare", "ddos-guard", "请开启javascript并刷新",
    "enable javascript and cookies to continue", "captcha-delivery",
    "incapsula incident id", "access denied", "radware",
)


@dataclass
class Fetched:
    url: str
    ua_name: str
    status: int | None = None
    length: int = 0
    text: str = ""
    final_url: str = ""
    elapsed_ms: int = 0
    error: str = ""
    headers: dict = field(default_factory=dict)

    @property
    def challenged(self) -> bool:
        low = self.text[:4000].lower()
        return any(m in low for m in CHALLENGE_MARKERS)

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error and not self.challenged


def fetch(url: str, ua: str = BROWSER_UA, ua_name: str = "browser",
          timeout: int = 20, max_bytes: int = 3_000_000) -> Fetched:
    """One polite GET. Never raises: transport failures come back as .error."""
    headers = dict(DEFAULT_HEADERS, **{"User-Agent": ua})
    started = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=timeout,
                         allow_redirects=True, stream=True)
        body = r.raw.read(max_bytes, decode_content=True) or b""
        text = body.decode(r.encoding or "utf-8", errors="replace")
        return Fetched(url=url, ua_name=ua_name, status=r.status_code,
                       length=len(body), text=text, final_url=r.url,
                       elapsed_ms=int((time.time() - started) * 1000),
                       headers={k.lower(): v for k, v in r.headers.items()})
    except Exception as e:  # noqa: BLE001 - a blocked probe is data, not a crash
        return Fetched(url=url, ua_name=ua_name,
                       elapsed_ms=int((time.time() - started) * 1000),
                       error=f"{type(e).__name__}: {e}")


def origin(url: str) -> str:
    p = urlparse(url if "://" in url else "https://" + url)
    return f"{p.scheme}://{p.netloc}"


def absolutise(base: str, href: str) -> str:
    return urljoin(base, href)
