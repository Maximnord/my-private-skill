---
name: ai-visibility-method
description: "Entry point and method layer for any site, URL or audit: decides which skill runs, in what order, and what counts as done. Routes AI-search questions to the geo-* skills and classic-search questions to the seo-* skills, then adds the checks both get wrong: strict RFC 9309 robots.txt parsing, AI crawlers blocked at the WAF or CDN, llms.txt link validation, passage citability in Hebrew and other non-Latin scripts, and a ticket loop that re-verifies fixes and catches regressions. Where it disagrees with geo-* or seo-*, this layer wins."
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

## Routing: which skill answers which question

Two axes, one method. This skill is the entry point: it picks the axis first, the
skill second. Where a `geo-*` or `seo-*` result disagrees with the checks here,
this layer wins.

**AI-search axis (`geo-*`)** - visibility inside AI answers.

| Question | Skill |
| --- | --- |
| Will an AI quote this page? | `geo-citability` (Hebrew or RTL: the scorer here) |
| Can AI crawlers reach the site? | `geo-crawlers` (strict cases: `robots_rfc9309.py`, `ai_ua_probe.py`) |
| Is llms.txt correct? | `geo-llmstxt` (link validation: here) |
| Why is the brand absent from AI answers? | `geo-brand-mentions` |
| Does the content carry E-E-A-T? | `geo-content` |
| Do the entities resolve? | `geo-schema` |
| Technical health for AI bots | `geo-technical` |
| One platform specifically | `geo-platform-optimizer` |
| Whole site at once | `geo-audit` |

**Classic-search axis (`seo-*`)** - ranking in Google's own results.

| Question | Skill |
| --- | --- |
| Does this schema type still earn rich results? | `seo-schema` |
| Keywords, multimedia, external links | `seo-content` |
| IndexNow, DataForSEO, fix deadlines | `seo-technical` |
| One page, every element | `seo-page` |
| Two languages on one domain | `seo-hreflang` |
| Images | `seo-images` |
| XML sitemaps | `seo-sitemap` |
| Strategy for a new or rebuilt site | `seo-plan` |
| Pages generated at scale from data | `seo-programmatic` |
| X vs Y and alternatives pages | `seo-competitor-pages` |
| Whole site at once | `seo-audit` |

**Israel layer (`hebrew-*`, `israeli-*`)** runs alongside either axis, never
instead of one: `hebrew-seo-geo-toolkit` for Hebrew morphology, `.co.il` and
Israeli business schema; `hebrew-document-generator` for any Hebrew deliverable;
`israeli-accessibility-compliance` for IS 5568.

### Pairs that extend each other

The axes are cut by question, not by object, so the same object appears on both
sides and the pair is complementary rather than competing:

| Object | Classic axis | AI axis |
| --- | --- | --- |
| Schema | `seo-schema`: which types Google still renders | `geo-schema`: entity recognition, sameAs, speakable |
| Content | `seo-content`: keywords, media, external links | `geo-content`: E-E-A-T, machine-parseable paragraphs |
| Technical | `seo-technical`: IndexNow, DataForSEO, deadlines | `geo-technical`: AI bot access, SSR, INP |
| Whole site | `seo-audit` | `geo-audit` |

A full engagement runs both sides of a row. Reporting one side as the whole
picture is the failure this routing exists to prevent.

## Update safety

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
