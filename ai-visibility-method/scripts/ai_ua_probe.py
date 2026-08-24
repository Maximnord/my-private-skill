#!/usr/bin/env python3
"""Detect WAF/CDN blocking of AI crawlers that robots.txt cannot reveal.

robots.txt is a request; the edge is the enforcement. Cloudflare Bot Fight,
Imperva, Akamai, Radware, AWS WAF and most Israeli hosting panels ship rules
that answer 403 or a JS challenge to non-browser user agents - while the site
owner sees a perfect page in their own browser. That gap is invisible to every
audit that fetches with a browser UA only.

Method: fetch the same URL once as a browser (baseline), then once per bot with
the vendor's real product token, sequentially and politely. Compare status,
body size and challenge markers.

Probe more than the home page. A page cache in front of the origin can make the
home page answer 200 to everything while every uncached URL - deep pages, new
pages, the sitemap - is answered by the origin, which may be configured very
differently. The cache column shows which of the two actually answered.

Usage:
    ai_ua_probe.py <url> [more urls ...] [--bots GPTBot,ClaudeBot] [--all] [--delay 1.5] [--json]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchlib import AI_USER_AGENTS, BROWSER_UA, CORE_BOTS, fetch  # noqa: E402

# Below this share of the baseline body the bot is being served a stub: a
# challenge page, an empty shell or a "your browser is not supported" notice.
SHRINK_RATIO = 0.60


def classify(baseline, probe) -> tuple[str, str]:
    if probe.error:
        return "ERROR", f"transport failure: {probe.error}"
    if probe.status in (401, 403, 405, 406, 429):
        return "BLOCKED", f"HTTP {probe.status} for this user agent while the browser gets {baseline.status}"
    if probe.status and probe.status >= 500 and baseline.status == 200:
        return "BLOCKED", f"HTTP {probe.status} for this user agent only"
    if probe.challenged and not baseline.challenged:
        return "CHALLENGED", "served a bot-challenge interstitial (JS/captcha) instead of the page"
    if probe.status != baseline.status:
        return "DIFFERENT", f"HTTP {probe.status} vs {baseline.status} for the browser"
    if baseline.length and probe.length < baseline.length * SHRINK_RATIO:
        pct = round(100 * probe.length / max(baseline.length, 1))
        return "THIN", f"body is {pct}% of the browser's ({probe.length} vs {baseline.length} bytes)"
    return "OK", f"HTTP {probe.status}, {probe.length} bytes"


def cache_state(res) -> str:
    """Which layer answered: the page cache or the origin."""
    ls = (res.headers.get("x-litespeed-cache") or "").lower()
    cf = (res.headers.get("cf-cache-status") or "").lower()
    if ls:
        return f"litespeed:{ls}"
    if cf in ("hit", "stale", "updating"):
        return f"cdn:{cf}"
    return "origin"


def probe(url: str, bots: list[str], delay: float = 1.5) -> dict:
    baseline = fetch(url, BROWSER_UA, "browser")
    out = {
        "url": url,
        "baseline": {"status": baseline.status, "bytes": baseline.length,
                     "challenged": baseline.challenged, "error": baseline.error,
                     "final_url": baseline.final_url},
        "results": {}, "verdict": "", "blocked": [],
        "baseline_cache": cache_state(baseline),
    }
    if baseline.error or baseline.status != 200:
        out["verdict"] = ("baseline fetch failed - the page itself is unreachable, "
                          "fix that before interpreting any bot result")
        return out

    for bot in bots:
        time.sleep(delay)
        res = fetch(url, AI_USER_AGENTS[bot], bot)
        status, detail = classify(baseline, res)
        out["results"][bot] = {
            "status": status, "detail": detail, "http": res.status,
            "bytes": res.length, "ms": res.elapsed_ms,
            "server": res.headers.get("server", ""),
            "cache": cache_state(res),
        }
        if status in ("BLOCKED", "CHALLENGED"):
            out["blocked"].append(bot)

    if all(r["cache"] != "origin" for r in out["results"].values()) and out["results"]:
        out["cache_warning"] = ("Every probe was answered by a page cache, so this says nothing about "
                                "how the origin treats crawlers. Re-run on an uncached URL - a deep "
                                "page, a brand-new URL, or the sitemap.")
    if out["blocked"]:
        out["verdict"] = ("P0 ACCESS LAYER FAILURE: " + ", ".join(out["blocked"]) +
                          " cannot read this page. Everything downstream - schema, "
                          "content, llms.txt - is invisible to those engines until this is fixed.")
    elif any(v["status"] in ("THIN", "DIFFERENT") for v in out["results"].values()):
        out["verdict"] = ("Bots receive a different response than browsers. Verify manually "
                          "whether the served body still contains the main content.")
    else:
        out["verdict"] = "No edge-level blocking detected for the probed bots."
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    urls = [a for a in argv if not a.startswith("--")]
    skip = set()
    for i, a in enumerate(argv):
        if a in ("--bots", "--delay") and i + 1 < len(argv):
            skip.add(argv[i + 1])
    urls = [u for u in urls if u not in skip]
    bots = list(AI_USER_AGENTS) if "--all" in argv else CORE_BOTS
    delay = 1.5
    for i, a in enumerate(argv):
        if a == "--bots" and i + 1 < len(argv):
            bots = [b.strip() for b in argv[i + 1].split(",") if b.strip() in AI_USER_AGENTS]
        if a == "--delay" and i + 1 < len(argv):
            delay = float(argv[i + 1])

    runs = [probe(u, bots, delay) for u in urls]
    if "--json" in argv:
        print(json.dumps(runs if len(runs) > 1 else runs[0], ensure_ascii=False, indent=2))
        return 0

    for data in runs:
        b = data["baseline"]
        print(f"probe: {data['url']}")
        print(f"  baseline (browser): HTTP {b['status']}, {b['bytes']} bytes, "
              f"answered by {data['baseline_cache']}"
              + (f"  [{b['error']}]" if b["error"] else ""))
        print()
        for bot, r in data["results"].items():
            print(f"  [{r['status']:<10}] {bot:<16} {r['cache']:<16} {r['detail']}")
        if data.get("cache_warning"):
            print(f"\n  NOTE: {data['cache_warning']}")
        print(f"\n  {data['verdict']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
