# The four-layer dependency model

A six-dimension score answers "how bad is it". It does not answer "what do I fix
first", and that is the question a client is paying for. The layer model answers
ordering, and it is the single most load-bearing idea in this skill.

```
ACCESS        can the crawler obtain the bytes?
   |
TARGETING     can it find and identify each URL?
   |
UNDERSTANDING can a machine tell what entity this is?
   |
CITABILITY    is there anything here worth quoting?
```

**Each layer depends on the one above it.** A page with flawless schema, perfect
E-E-A-T signals and a beautiful FAQ block is worth exactly zero if the WAF answers
403 to GPTBot. Always fix the topmost failing layer before spending a single hour
on the layers below it. Report findings in this order too - a client who reads
"add a definition block" above "your CDN blocks every AI crawler" will work on the
wrong thing.

---

## Layer 1 - Access

**Question:** can the crawler obtain the bytes?

| Check | How | Failure code |
|---|---|---|
| robots.txt grants the AI product tokens | `scripts/robots_rfc9309.py <url>` | ROBOTS_BLOCKED |
| The edge actually serves those tokens | `scripts/ai_ua_probe.py <url>` | WAF_BLOCKED |
| No noindex - in the meta tag AND the X-Robots-Tag header | header check | NOINDEX |
| Body text exists in the static HTML | `scripts/passage_audit.py <url>` | EMPTY_SHELL |
| Page returns 200, not 202/3xx/403 | any fetch | PAGE_UNREACHABLE |

Three access failures are near-invisible to the site owner and therefore turn up
in almost every first audit:

1. **The wildcard blanket block.** `User-agent: * / Disallow: /` inherited from a
   staging config or a legacy SEO plugin. Every AI crawler without a group of its
   own is blocked by it. Owners read their robots.txt, see a rule they do not
   recognise as an AI rule, and move on.
2. **The edge, not the file.** robots.txt is a request; the WAF is enforcement.
   Cloudflare Bot Fight Mode, Imperva, Radware and most Israeli hosting control
   panels ship rules that 403 or challenge non-browser user agents. Nothing in the
   browser reveals it. This is what `ai_ua_probe.py` exists for, and it is
   routinely the highest-value finding in an engagement.
3. **The header-level noindex.** Injected globally by a CDN worker or middleware,
   absent from the page source. Check response headers, not just the HTML.

4. **The page cache masks the origin.** A CDN or page cache in front of the site
   answers popular URLs with a healthy 200 while every cache miss goes to an
   origin that may be configured completely differently. Observed in the field:
   a site where every URL served from the LiteSpeed cache returned 200 and every
   uncached URL - all service pages, contact, the blog articles and the sitemap
   declared in robots.txt - returned **429**. A browsing human only ever sees the
   warm pages. Always probe at least one deep or brand-new URL, never the home
   page alone: `ai_ua_probe.py <home> <deep-url> <sitemap-url>`. The cache column
   in the output says which layer answered.

**Assume AI crawlers do not execute JavaScript.** Googlebot renders, on a delayed
queue. GPTBot, ClaudeBot, PerplexityBot and OAI-SearchBot are best treated as
plain-HTML fetchers. A client-side-rendered SPA is, to them, a blank page.

Before reporting EMPTY_SHELL, run `ai_ua_probe.py`: a WAF stub and a JS shell look
identical to a fetcher, and the remediation is completely different.

## Layer 2 - Targeting

**Question:** can the engine find and identify each URL?

- `sitemap.xml` exists, is declared in robots.txt, and contains only canonical
  pages worth citing. Faceted, paginated, session-parameter and internal-search
  URLs must be excluded - low-value URLs in the index dilute the entity.
- `canonical` points at the page itself, not at a parent or the home page.
- `llms.txt`, if present, must be structurally valid AND its links must resolve
  and be crawlable: `scripts/llmstxt_verify.py <url>`. A file pointing at 404s or
  robots-blocked paths is worse than no file - it spends crawl budget on dead ends.
- **Missing URLs must return 404 or 410 - never 429 or 503.** A 429 means "slow
  down", so the crawler backs off across the whole site and keeps the dead URL on
  its list instead of dropping it. Some hosting stacks answer 429 for anything not
  found; check with a deliberately nonexistent path, because nobody discovers this
  through a browser.
- Multilingual sites: reciprocal hreflang between every language version. Without
  it the versions compete as duplicates and the wrong language is retrieved for
  the market. For an English/Hebrew site this is a targeting-layer P1, not a
  nice-to-have.

## Layer 3 - Understanding

**Question:** can a machine tell what entity this is?

- JSON-LD present, valid, and consistent with the visible content. Schema that
  contradicts the page is worse than no schema.
- Organization with `sameAs` pointing at the profiles the models already know:
  Wikipedia/Wikidata where it exists, LinkedIn, Crunchbase, the relevant national
  registries and directories.
- One canonical brand name, plus every alias and common misspelling, used
  consistently. Entity disambiguation is the foundation: if the model cannot tell
  which company is meant, nothing downstream can be attributed correctly.
- A page in the market's native language. A Hebrew-market brand with English-only
  content is an understanding-layer failure, not a content preference.

## Layer 4 - Citability

**Question:** is there anything here worth quoting?

This is where length, structure, extractable blocks, authority signals and
question-relevance live. See `content-blocks.md`. Measure it with
`scripts/passage_audit.py`, which scores per passage rather than per page.

---

## Reporting rule

State the failing layer, then the finding, then the evidence, then the fix. Never
mix layers in a single priority list without saying which layer each item belongs
to - the client cannot see the dependency, and will optimise the cheapest item
first.

## Provenance

The layer framing is adapted from the GEO Readiness Manual via the GeoLook skill
(MIT, see `ATTRIBUTION.md`). The crawler-rendering behaviour and the access-failure
patterns are consistent with what the vendors document about their crawlers and
with what `ai_ua_probe.py` finds in practice. Verify each claim against the live
site before putting it in a client document.
