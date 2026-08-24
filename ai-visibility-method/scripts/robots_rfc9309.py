#!/usr/bin/env python3
"""robots.txt evaluation with RFC 9309 group semantics.

Line-by-line regex parsers (the common shortcut) report "ALLOWED" for at least
three real-world blocking patterns. This module implements the actual spec:

  1. A group is one or more CONSECUTIVE user-agent lines plus the rules that
     follow. Several user-agent lines share one rule set, so attributing rules
     only to the last token silently un-blocks every earlier bot in the group.
  2. Product tokens are matched case-insensitively, by longest matching prefix.
     `user-agent: gptbot` is valid and must bind GPTBot.
  3. Specificity beats order: when any group matches the crawler by name, the
     `*` group is ignored entirely - even if `*` says Disallow: / .
  4. Inside the winning group the longest matching path wins, Allow breaking ties.

Usage:
    robots_rfc9309.py <url|path-to-robots.txt> [--bots GPTBot,ClaudeBot] [--path /he/] [--json]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchlib import CORE_BOTS, AI_USER_AGENTS, fetch, origin  # noqa: E402

KNOWN_BOTS = list(AI_USER_AGENTS.keys()) + [
    "anthropic-ai", "Claude-SearchBot", "GoogleOther", "Googlebot",
    "Applebot-Extended", "Meta-ExternalAgent", "FacebookBot", "cohere-ai",
    "DuckAssistBot", "PetalBot", "YouBot", "Diffbot", "Timpibot",
]


@dataclass
class Rule:
    allow: bool
    path: str
    pattern: re.Pattern

    def matches(self, target: str) -> bool:
        return bool(self.pattern.match(target))

    @property
    def specificity(self) -> int:
        return len(self.path)


@dataclass
class Group:
    tokens: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)


def _compile(path: str) -> re.Pattern:
    """robots path -> regex. `*` is any run of characters, `$` anchors the end."""
    anchored = path.endswith("$")
    body = path[:-1] if anchored else path
    out = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile("^" + out + ("$" if anchored else ""))


def parse(text: str) -> dict:
    groups: list[Group] = []
    sitemaps: list[str] = []
    other: list[tuple[str, str]] = []
    current: Group | None = None
    collecting_agents = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()

        if field_name == "user-agent":
            # A user-agent line after rules opens a NEW group; consecutive
            # user-agent lines extend the current one.
            if current is None or not collecting_agents:
                current = Group()
                groups.append(current)
            current.tokens.append(value)
            collecting_agents = True
        elif field_name in ("allow", "disallow"):
            collecting_agents = False
            if current is None:
                continue  # rules before any user-agent line are not addressed to anyone
            if value == "":
                # "Disallow:" with an empty value means "nothing is disallowed".
                continue
            current.rules.append(
                Rule(allow=field_name == "allow", path=value, pattern=_compile(value))
            )
        elif field_name == "sitemap":
            sitemaps.append(value)
        else:
            other.append((field_name, value))

    return {"groups": groups, "sitemaps": sitemaps, "other": other}


def select_group(groups: list[Group], crawler: str) -> tuple[list[Rule], str, str]:
    """Return (rules, matched_token, source) for one crawler.

    Groups sharing the winning token are merged, per RFC 9309 section 2.2.1.
    """
    name = crawler.lower()
    best_len = -1
    best_token = ""
    for g in groups:
        for tok in g.tokens:
            t = tok.strip().lower()
            if t == "*":
                continue
            if name.startswith(t) and len(t) > best_len:
                best_len, best_token = len(t), t
    if best_token:
        rules = [r for g in groups
                 if any(tok.strip().lower() == best_token for tok in g.tokens)
                 for r in g.rules]
        return rules, best_token, "specific-group"

    wildcard = [r for g in groups if any(tok.strip() == "*" for tok in g.tokens)
                for r in g.rules]
    if wildcard:
        return wildcard, "*", "wildcard-group"
    return [], "", "no-group"


def decide(rules: list[Rule], target: str = "/") -> tuple[bool, str]:
    """Longest match wins; Allow wins ties; no match means allowed."""
    winner: Rule | None = None
    for r in rules:
        if not r.matches(target):
            continue
        if (winner is None
                or r.specificity > winner.specificity
                or (r.specificity == winner.specificity and r.allow and not winner.allow)):
            winner = r
    if winner is None:
        return True, "no matching rule"
    verb = "Allow" if winner.allow else "Disallow"
    return winner.allow, f"{verb}: {winner.path}"


def evaluate(text: str, bots: list[str] | None = None, path: str = "/") -> dict:
    bots = bots or CORE_BOTS
    parsed = parse(text)
    groups: list[Group] = parsed["groups"]
    result = {"path_tested": path, "sitemaps": parsed["sitemaps"],
              "bots": {}, "traps": [], "group_count": len(groups)}

    for bot in bots:
        rules, token, source = select_group(groups, bot)
        allowed, reason = decide(rules, path)
        root_allowed, root_reason = decide(rules, "/")
        blocked_paths = sorted({r.path for r in rules if not r.allow})
        if not allowed:
            status = "BLOCKED"
        elif blocked_paths:
            status = "ALLOWED_WITH_EXCLUSIONS"
        else:
            status = "ALLOWED"
        result["bots"][bot] = {
            "status": status,
            "allowed": allowed,
            "matched_by": token or "(none)",
            "rule_source": source,
            "reason": reason,
            "root_allowed": root_allowed,
            "root_reason": root_reason,
            "disallowed_paths": blocked_paths[:20],
        }

    # --- traps: the patterns that naive parsers get wrong -------------------
    for g in groups:
        ai_tokens = [t for t in g.tokens
                     if any(t.strip().lower() == k.lower() for k in KNOWN_BOTS)]
        if len(g.tokens) > 1 and ai_tokens:
            result["traps"].append({
                "type": "SHARED_GROUP",
                "detail": f"One rule set is shared by {len(g.tokens)} user-agent lines "
                          f"({', '.join(g.tokens)}). Line-by-line parsers attribute the "
                          f"rules to the last token only and report the others as allowed.",
            })
        for tok in g.tokens:
            canon = next((k for k in KNOWN_BOTS if k.lower() == tok.strip().lower()), None)
            if canon and tok.strip() != canon:
                result["traps"].append({
                    "type": "CASE_VARIANT_TOKEN",
                    "detail": f"'{tok}' is a valid case-insensitive form of '{canon}'. "
                              f"Case-sensitive parsers miss this group entirely.",
                })

    for bot, info in result["bots"].items():
        if info["rule_source"] == "wildcard-group" and not info["root_allowed"]:
            result["traps"].append({
                "type": "WILDCARD_BLANKET_BLOCK",
                "detail": f"{bot} has no group of its own and inherits 'User-agent: *' "
                          f"({info['root_reason']}). This is the most common unintentional "
                          f"AI block - usually inherited from a legacy SEO config.",
            })

    seen, unique = set(), []
    for t in result["traps"]:
        key = (t["type"], t["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    result["traps"] = unique
    return result


def load(target: str) -> tuple[str, str]:
    p = Path(target)
    if p.exists():
        return p.read_text("utf-8", errors="replace"), str(p)
    url = target if target.rstrip("/").endswith("robots.txt") else origin(target) + "/robots.txt"
    res = fetch(url, ua_name="browser")
    if res.error:
        raise SystemExit(f"could not fetch {url}: {res.error}")
    if res.status == 404:
        return "", url  # no robots.txt at all == everything allowed
    if res.status != 200:
        raise SystemExit(f"{url} returned HTTP {res.status}")
    return res.text, url


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    target = argv[0]
    bots = CORE_BOTS
    path = "/"
    as_json = "--json" in argv
    for i, a in enumerate(argv):
        if a == "--bots" and i + 1 < len(argv):
            bots = [b.strip() for b in argv[i + 1].split(",") if b.strip()]
        if a == "--path" and i + 1 < len(argv):
            path = argv[i + 1]

    text, source = load(target)
    data = evaluate(text, bots, path)
    data["source"] = source
    if not text.strip():
        data["note"] = "no robots.txt found - all crawlers are allowed by default"

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"robots.txt: {source}   (groups: {data['group_count']}, path tested: {path})")
    if data.get("note"):
        print(f"  note: {data['note']}")
    print()
    for bot, info in data["bots"].items():
        mark = {"ALLOWED": "OK  ", "ALLOWED_WITH_EXCLUSIONS": "PART", "BLOCKED": "BLOCK"}[info["status"]]
        print(f"  [{mark}] {bot:<16} via {info['rule_source']:<15} {info['reason']}")
    if data["sitemaps"]:
        print("\n  sitemaps: " + ", ".join(data["sitemaps"][:5]))
    if data["traps"]:
        print("\n  TRAPS DETECTED")
        for t in data["traps"]:
            print(f"   - {t['type']}: {t['detail']}")
    print("\n  robots permission is necessary, not sufficient: run ai_ua_probe.py "
          "to see whether the WAF/CDN answers these bots at all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
