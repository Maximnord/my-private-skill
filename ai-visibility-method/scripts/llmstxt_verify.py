#!/usr/bin/env python3
"""Validate an existing llms.txt: structure, and whether its links actually work.

Generating llms.txt is the easy half. A file that points at 404s, redirects or
robots-blocked paths hands the model a broken map, which is worse than no map:
the crawler spends its budget on dead ends and learns nothing about the brand.
This checks the half that generators skip.

Usage:
    llmstxt_verify.py <site-url|path-to-llms.txt> [--limit 25] [--delay 0.8] [--json]
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots_rfc9309 as R  # noqa: E402
from fetchlib import BROWSER_UA, absolutise, fetch, origin  # noqa: E402

LINK = re.compile(r"\[([^\]]{1,200})\]\(([^)\s]+)\)")


def parse_llms_txt(text: str, base: str) -> dict:
    lines = text.splitlines()
    title = ""
    summary = ""
    sections: list[str] = []
    links: list[dict] = []
    current = "(top)"
    for ln in lines:
        s = ln.strip()
        if s.startswith("# ") and not title:
            title = s[2:].strip()
        elif s.startswith("> ") and not summary:
            summary = s[2:].strip()
        elif s.startswith("## "):
            current = s[3:].strip()
            sections.append(current)
        for m in LINK.finditer(ln):
            links.append({"label": m.group(1), "url": absolutise(base, m.group(2)),
                          "raw": m.group(2), "section": current})
    return {"title": title, "summary": summary, "sections": sections, "links": links}


def verify(target: str, limit: int = 25, delay: float = 0.8) -> dict:
    p = Path(target)
    if p.exists():
        text, source, base = p.read_text("utf-8", errors="replace"), str(p), ""
    else:
        base = origin(target)
        source = target if target.endswith(".txt") else base + "/llms.txt"
        res = fetch(source, BROWSER_UA)
        if res.error:
            return {"source": source, "exists": False, "error": res.error}
        if res.status in (429, 503) or (res.status or 0) >= 500:
            return {"source": source, "exists": None, "http": res.status,
                    "verdict": f"INCONCLUSIVE: HTTP {res.status}. The server is rate limiting or "
                               f"erroring, which is not the same as the file being absent. Wait and "
                               f"retry with a longer --delay before reporting anything about llms.txt."}
        if res.status != 200:
            return {"source": source, "exists": False, "http": res.status,
                    "verdict": f"no llms.txt (HTTP {res.status}). Generate one only after the "
                               f"access layer is clean - an llms.txt on a WAF-blocked site is inert."}
        text = res.text

    parsed = parse_llms_txt(text, base or "https://example.com")
    out = {"source": source, "exists": True, "title": parsed["title"],
           "summary_present": bool(parsed["summary"]), "sections": parsed["sections"],
           "link_count": len(parsed["links"]), "checked": [], "structure_issues": [],
           "dead": [], "blocked": [], "redirected": []}

    if not parsed["title"]:
        out["structure_issues"].append("missing the required '# Title' first line")
    if not parsed["summary"]:
        out["structure_issues"].append("missing the '> one-line summary' blockquote")
    if not parsed["sections"]:
        out["structure_issues"].append("no '## Section' headings - the file is an undifferentiated list")
    if not parsed["links"]:
        out["structure_issues"].append("no markdown links at all - nothing for a crawler to follow")

    robots_txt = ""
    if base:
        try:
            robots_txt, _ = R.load(base)
        except SystemExit:
            robots_txt = ""

    seen = set()
    for link in parsed["links"]:
        if link["url"] in seen or len(out["checked"]) >= limit:
            continue
        seen.add(link["url"])
        time.sleep(delay)
        res = fetch(link["url"], BROWSER_UA)
        path = urlparse(link["url"]).path or "/"
        robots_ok = True
        robots_reason = "not checked"
        if robots_txt:
            ev = R.evaluate(robots_txt, ["GPTBot"], path)
            robots_ok = ev["bots"]["GPTBot"]["allowed"]
            robots_reason = ev["bots"]["GPTBot"]["reason"]
        row = {"url": link["url"], "section": link["section"], "http": res.status,
               "bytes": res.length, "error": res.error, "robots_allows_gptbot": robots_ok,
               "robots_reason": robots_reason,
               "redirected": bool(res.final_url and res.final_url.rstrip("/") != link["url"].rstrip("/"))}
        out["checked"].append(row)
        if res.error or (res.status or 0) >= 400:
            out["dead"].append(link["url"])
        if not robots_ok:
            out["blocked"].append(link["url"])
        if row["redirected"]:
            out["redirected"].append({"from": link["url"], "to": res.final_url})

    problems = len(out["dead"]) + len(out["blocked"])
    if problems == 0 and not out["structure_issues"]:
        out["verdict"] = "llms.txt is structurally valid and every checked link resolves and is crawlable."
    else:
        out["verdict"] = (f"{len(out['dead'])} dead link(s), {len(out['blocked'])} robots-blocked link(s), "
                          f"{len(out['structure_issues'])} structure issue(s). Fix before promoting the file - "
                          f"a broken map costs more than no map.")
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    limit, delay = 25, 0.8
    for i, a in enumerate(argv):
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if a == "--delay" and i + 1 < len(argv):
            delay = float(argv[i + 1])

    data = verify(argv[0], limit, delay)
    if "--json" in argv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"llms.txt: {data['source']}")
    if data.get("exists") is not True:
        print(f"  {data.get('verdict') or data.get('error')}")
        return 0
    print(f"  title: {data['title'] or '(missing)'}   sections: {len(data['sections'])}   "
          f"links: {data['link_count']} (checked {len(data['checked'])})")
    for s in data["structure_issues"]:
        print(f"   STRUCTURE: {s}")
    for row in data["checked"]:
        flag = "OK   "
        if row["error"] or (row["http"] or 0) >= 400:
            flag = "DEAD "
        elif not row["robots_allows_gptbot"]:
            flag = "BLOCK"
        elif row["redirected"]:
            flag = "REDIR"
        print(f"   [{flag}] {str(row['http']):<4} {row['url'][:80]}")
    print(f"\n  {data['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
