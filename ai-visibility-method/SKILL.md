---
name: ai-visibility-method
description: Method layer and hardened checks for AI-search visibility (GEO) work: RFC 9309 robots.txt evaluation, WAF/CDN detection of blocked AI crawlers, llms.txt link validation, passage-level citability auditing with Hebrew and RTL support, and a ticket loop that re-verifies fixes and flags regressions. This skill should be used whenever a GEO or AI-visibility audit is run, whenever AI crawler access or robots.txt is checked, whenever a page in Hebrew, Arabic, Russian or any non-Latin script is audited for AI citability, whenever llms.txt is validated, and whenever client fixes need machine-checkable acceptance criteria or a monthly re-verification cycle. It complements the geo and seo skills rather than replacing them: use those for reporting, proposals and deliverables, and this one for ordering findings, for the checks those skills get wrong, and for the discipline that keeps numbers defensible.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# AI visibility: method and hardened checks

## Purpose

Two things that generic GEO tooling gets wrong, and one it usually skips:

1. **Ordering.** A flat list of findings makes clients fix the cheapest item.
   Findings must be ordered by the four-layer dependency model - nothing below a
   failing layer is visible to any engine.
2. **Correctness of the checks themselves.** The common robots.txt parser reports
   "allowed" for real blocks; almost nothing probes the WAF; and non-Latin pages
   are scored as empty. A confidently wrong audit in a client deliverable is worse
   than no audit.
3. **Verification.** A fix nobody re-checks is a promise. Tickets carry
   machine-checkable acceptance criteria and are re-run every cycle.

## When to use this skill

Load it at the start of any GEO/AI-visibility engagement, and specifically when:

- checking whether AI crawlers can reach a site (robots.txt, WAF, rendering)
- auditing a Hebrew, bilingual or other non-Latin-script page for citability
- validating or generating llms.txt
- turning audit findings into a client action plan
- running a monthly re-check for an existing client

Do not use it for keyword research, paid media, or writing the deliverable
document - `geo-report`, `geo-report-pdf`, `geo-proposal`, `geo-compare`,
`hebrew-seo-geo-toolkit` and `hebrew-content-writer` already cover those.

## Workflow

### Step 1 - Read the method before judging anything

Read `references/four-layer-model.md` first, always. It determines the order of
everything that follows. Then read the reference that matches the task:

| Task | Reference |
|---|---|
| Ordering findings, writing the action plan | `references/priority-and-risk.md` |
| Sampling AI answers, reporting visibility numbers | `references/sampling-discipline.md` |
| Rewriting pages, Hebrew/RTL content work | `references/content-blocks.md` |

Rule inherited with the method: **every recommendation must trace to a section in
these files.** A recommendation that cannot be traced does not go in the document.

### Step 2 - Access layer (run these before anything else)

```bash
cd ~/.claude/skills/ai-visibility-method
python3 scripts/robots_rfc9309.py https://client.co.il          # add --json for machine output
python3 scripts/ai_ua_probe.py    https://client.co.il https://client.co.il/deep-page/ \
                                  https://client.co.il/sitemap_index.xml   # ~1.5s per bot per URL
```

`robots_rfc9309.py` implements RFC 9309 group semantics and reports the three
patterns that line-by-line parsers miss: shared user-agent groups, case-variant
tokens, and wildcard blanket blocks. `ai_ua_probe.py` fetches the page as each
crawler's real product token and compares against a browser baseline - this is
what catches Cloudflare/Imperva/Radware rules that are invisible in a browser.

Probe more than the home page. A page cache in front of the origin makes the home
page answer 200 for everyone while every cache miss - deep pages, new pages, the
sitemap - is answered by the origin, which may block or rate-limit. The cache
column shows which layer answered; a verdict built only on cache hits is worthless.
Also request a deliberately nonexistent URL: it must return 404, not 429.

If either reports a block, that is the finding. Stop, report it as P0, and do not
present content recommendations as if they mattered yet.

### Step 3 - Page layer

```bash
python3 scripts/passage_audit.py https://client.co.il/he/service   # --lang he to force
python3 scripts/llmstxt_verify.py https://client.co.il
```

`passage_audit.py` counts words in a script-aware way (Hebrew, Arabic, Cyrillic,
Latin, CJK), detects the five extractable blocks with per-language pattern packs,
and scores each section for whether it can be quoted on its own. It also flags
missing `dir="rtl"` and `lang` mismatches on Hebrew pages.

**Always confirm an `EMPTY_SHELL` finding with `ai_ua_probe.py` before reporting
it.** A WAF stub and a JavaScript-only shell look identical to a fetcher, and the
two fixes are unrelated.

### Step 4 - Tickets with acceptance criteria

Copy `assets/tickets.template.json` into the client's working folder and write one
ticket per fix. Each ticket needs a layer, a priority, a risk level, an owner, a
basis (which reference section justifies it), and a `check` that a machine can
decide. Anything a machine cannot decide is typed `manual` and is never
auto-completed.

```bash
python3 scripts/verify_tickets.py <client>/tickets.json            # dry run
python3 scripts/verify_tickets.py <client>/tickets.json --write    # persist statuses
```

Passing checks flip to `done`; a check that stops passing flips `done` back to
`regressed`. Regressions are the point: deploys, CDN rule changes and CMS
migrations silently revert GEO fixes, and nobody notices without this.

Supported check types are listed in the script's docstring - `robots_allows`,
`ua_probe`, `http_status`, `has_jsonld`, `min_words`, `has_block`,
`quotable_passages`, `llmstxt_valid`, `contains`, `manual`.

### Step 5 - Report

Hand the JSON output to whichever reporting skill produces the deliverable.
Structure the findings by layer, state priority and risk separately for each, and
carry the non-negotiables from `references/sampling-discipline.md` into the
document: no engine can be promised a citation; visibility numbers are per
platform and per market, never averaged; attribution is "observed correlation"
unless a controlled comparison exists.

## Relationship to the installed geo-* skills

`geo-update` overwrites everything under `~/.claude/skills/geo/` and
`~/.claude/skills/geo-*/` from its upstream repository. This skill sits outside
that namespace deliberately, so it survives updates. Two known defects in the
installed `geo` toolkit that the scripts here work around rather than patch:

- `geo/scripts/fetch_page.py` parses robots.txt line by line and matches product
  tokens case-sensitively, so shared user-agent groups and lowercase tokens are
  reported as allowed. Use `robots_rfc9309.py` for any client-facing statement
  about crawler access.
- The same file defines AI crawler user agents but never fetches with them, so no
  edge-level blocking is detected anywhere in that toolkit. Use `ai_ua_probe.py`.

## Constraints

- Requires `requests` and `beautifulsoup4` (present in the system Python).
- All scripts are read-only against the target site and fetch sequentially with a
  delay. Do not remove the delay for client sites.
- Run the test suite after editing any script:
  `python3 -m unittest discover -s tests -t .` (52 tests, offline, ~0.03s).
- Provenance and licensing of the method layer: `ATTRIBUTION.md`.
