#!/usr/bin/env python3
"""Re-check tickets against the live site and flip their status automatically.

This is the line between a service and an opinion. A ticket whose completion
cannot be re-verified by a machine is a promise; a ticket that a checker
re-confirms every cycle is a state. Regression matters as much as completion:
when a fix is reverted by a deploy, a CDN rule or a CMS migration, the ticket
must fall back to `regressed` on its own, not wait for someone to notice.

Checks that no machine can decide (a directory listing approved, a journalist
citing the brand) carry type "manual" and are never flipped automatically.

Usage:
    verify_tickets.py <tickets.json> [--write] [--only T-003] [--delay 1.0] [--json]

Ticket check types:
    robots_allows      {bot, path}          robots.txt grants this crawler the path
    ua_probe           {url, bot}           the edge actually serves that crawler
    http_status        {url, expect}        page returns the expected status
    has_jsonld         {url, type}          JSON-LD of that @type is present
    min_words          {url, min}           body text reaches the word threshold
    has_block          {url, block, lang}   definition/numbers/comparison/howto/faq present
    quotable_passages  {url, min}           at least N self-contained passages
    llmstxt_valid      {url}                llms.txt exists, is valid and links resolve
    contains           {url, text}          literal string present in the served HTML
    manual             {note}               human confirmation required
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llmstxt_verify as L  # noqa: E402
import passage_audit as P  # noqa: E402
import robots_rfc9309 as R  # noqa: E402
from fetchlib import AI_USER_AGENTS, BROWSER_UA, fetch  # noqa: E402
from ai_ua_probe import classify  # noqa: E402

_page_cache: dict[str, object] = {}


def get_page(url: str):
    if url not in _page_cache:
        _page_cache[url] = fetch(url, BROWSER_UA)
    return _page_cache[url]


def run_check(check: dict) -> tuple[str, str]:
    """Return (PASS|FAIL|MANUAL|ERROR, detail)."""
    kind = check.get("type", "manual")
    p = check.get("params", {})
    try:
        if kind == "manual":
            return "MANUAL", p.get("note", "requires human confirmation")

        if kind == "robots_allows":
            text, src = R.load(p["url"] if "url" in p else p["site"])
            ev = R.evaluate(text, [p.get("bot", "GPTBot")], p.get("path", "/"))
            info = ev["bots"][p.get("bot", "GPTBot")]
            return ("PASS" if info["allowed"] else "FAIL",
                    f"{info['rule_source']}: {info['reason']} ({src})")

        if kind == "ua_probe":
            bot = p.get("bot", "GPTBot")
            base = fetch(p["url"], BROWSER_UA, "browser")
            res = fetch(p["url"], AI_USER_AGENTS[bot], bot)
            status, detail = classify(base, res)
            return ("PASS" if status == "OK" else "FAIL", f"{bot}: {status} - {detail}")

        if kind == "http_status":
            res = get_page(p["url"])
            expect = int(p.get("expect", 200))
            return ("PASS" if res.status == expect else "FAIL",
                    f"HTTP {res.status} (expected {expect})")

        if kind == "has_jsonld":
            res = get_page(p["url"])
            data = P.audit(res.text, "auto", p["url"])
            types = [t.lower() for t in data["meta"]["jsonld_types"]]
            want = p["type"].lower()
            return ("PASS" if want in types else "FAIL",
                    f"JSON-LD types found: {data['meta']['jsonld_types'] or 'none'}")

        if kind == "min_words":
            res = get_page(p["url"])
            data = P.audit(res.text, p.get("lang", "auto"), p["url"])
            need = int(p.get("min", 1000))
            return ("PASS" if data["word_count"] >= need else "FAIL",
                    f"{data['word_count']} words (need {need}, language {data['language_detected']})")

        if kind == "has_block":
            res = get_page(p["url"])
            data = P.audit(res.text, p.get("lang", "auto"), p["url"])
            block = p["block"]
            return ("PASS" if data["blocks"].get(block) else "FAIL",
                    f"blocks present: {[k for k, v in data['blocks'].items() if v] or 'none'}")

        if kind == "quotable_passages":
            res = get_page(p["url"])
            data = P.audit(res.text, p.get("lang", "auto"), p["url"])
            need = int(p.get("min", 3))
            return ("PASS" if data["sections_quotable"] >= need else "FAIL",
                    f"{data['sections_quotable']} quotable of {data['sections_total']} sections (need {need})")

        if kind == "llmstxt_valid":
            data = L.verify(p["url"], limit=int(p.get("limit", 10)), delay=float(p.get("delay", 0.5)))
            ok = data.get("exists") and not data.get("dead") and not data.get("blocked") \
                and not data.get("structure_issues")
            return ("PASS" if ok else "FAIL", data.get("verdict", ""))

        if kind == "contains":
            res = get_page(p["url"])
            found = p["text"] in res.text
            return ("PASS" if found else "FAIL", f"literal {'found' if found else 'not found'}")

        return "ERROR", f"unknown check type '{kind}'"
    except Exception as e:  # noqa: BLE001 - a broken check must not abort the cycle
        return "ERROR", f"{type(e).__name__}: {e}"


def transition(old: str, result: str) -> str:
    if result == "PASS":
        return "done"
    if result == "FAIL":
        return "regressed" if old == "done" else (old if old in ("todo", "doing") else "todo")
    return old  # MANUAL / ERROR never change state


def verify(path: Path, only: str | None = None, write: bool = False,
           delay: float = 1.0) -> dict:
    doc = json.loads(path.read_text("utf-8"))
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    summary = {"checked": 0, "done": 0, "regressed": 0, "open": 0, "manual": 0, "errors": 0}
    rows = []

    for t in doc.get("tickets", []):
        if only and t.get("id") != only:
            continue
        old = t.get("status", "todo")
        if rows and delay:
            time.sleep(delay)  # a checker that trips the target's rate limiter reports false failures
        result, detail = run_check(t.get("check", {"type": "manual"}))
        new = transition(old, result)
        summary["checked"] += 1
        if result == "MANUAL":
            summary["manual"] += 1
        elif result == "ERROR":
            summary["errors"] += 1
        if new == "done":
            summary["done"] += 1
        elif new == "regressed":
            summary["regressed"] += 1
        elif new in ("todo", "doing"):
            summary["open"] += 1

        if new != old or result in ("PASS", "FAIL"):
            t.setdefault("history", []).append(
                {"at": stamp, "result": result, "detail": detail, "from": old, "to": new})
            t["history"] = t["history"][-20:]
        t["status"] = new
        t["last_checked"] = stamp
        rows.append({"id": t.get("id"), "title": t.get("title", ""), "priority": t.get("priority", ""),
                     "risk": t.get("risk", ""), "layer": t.get("layer", ""),
                     "result": result, "from": old, "to": new, "detail": detail})

    doc["updated"] = stamp
    if write:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), "utf-8")
    return {"file": str(path), "written": write, "summary": summary, "rows": rows}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    only, delay = None, 1.0
    for i, a in enumerate(argv):
        if a == "--only" and i + 1 < len(argv):
            only = argv[i + 1]
        if a == "--delay" and i + 1 < len(argv):
            delay = float(argv[i + 1])
    data = verify(Path(argv[0]), only, "--write" in argv, delay)

    if "--json" in argv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    s = data["summary"]
    print(f"{data['file']}  ({'saved' if data['written'] else 'dry run - pass --write to persist'})")
    print(f"  checked {s['checked']}: done {s['done']}, regressed {s['regressed']}, "
          f"open {s['open']}, manual {s['manual']}, errors {s['errors']}\n")
    for r in data["rows"]:
        arrow = f"{r['from']} -> {r['to']}" if r["from"] != r["to"] else r["to"]
        print(f"  [{r['result']:<6}] {r['id']:<7} {r['priority']:<3} {r['title'][:48]:<48} {arrow}")
        print(f"            {r['detail'][:110]}")
    if s["regressed"]:
        print("\n  REGRESSIONS: a previously accepted fix is gone. Treat as P0 for this cycle and "
              "find the deploy, CDN rule or CMS change that reverted it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
