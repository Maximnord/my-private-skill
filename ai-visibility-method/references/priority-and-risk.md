# Priority and risk are two separate axes

Priority says how much a fix is worth. Risk says how carefully to touch it. They
are independent, and collapsing them into one number is how audits produce plans
that either move nothing or break something.

Unblocking robots.txt is P0 **and** high risk: it is the most valuable fix on the
list and one wrong line takes the whole site out of every index. Adding a
definition block to a page is P1 and low risk. Both facts must appear on the
ticket.

---

## Axis 1 - Priority

Order findings this way. Do not reorder by what is cheapest to do.

1. **P0 - access-layer failures.** robots block, WAF block, JS-only shell, page
   unreachable, header-level noindex. While any of these holds, everything below
   is invisible to the engine, so no other work can be justified.
2. **P0 - factual errors in AI answers.** The model states the wrong industry,
   the wrong price, the wrong founder, or confuses the brand with a same-named
   company. This actively costs deals and it compounds: wrong facts get copied
   between sources. Fix the fact layer first - the site's own statements, then
   the external sources the model actually cites.
3. **P1 - extractable-block gaps.** No definition, no figures, no comparison, no
   steps anywhere on the site. See `content-blocks.md`.
4. **P1 - high-value questions with nothing to answer them.** Questions with
   buyer intent (recommendation, comparison, alternatives, pricing) where the site
   has no page that answers the question in the question's own words.
5. **P1 - external sources.** Directories, listicles, review sites, industry
   media, community platforms - the places the engine actually cites. This is P1,
   not P2. See the warning below.
6. **P2 - long-tail expansion.** More pages, more questions, more coverage.

### Why external sources rank this high - and how to justify it locally

The Chinese CN-GEO dataset (187,818 deduplicated citations) found brand-owned
sites accounted for **1.37%** of all citations, against 16.4% for content
platforms, 13.6% for news media and 9.1% for ranking and recommendation sites.
The operational conclusion drawn there: the brand's own site is a **fact source**,
not a citation source. Taking the home page from 60 to 90 points returns less
than winning one entry on a site the engine already cites.

**Do not transfer that 1.37% to another market as if it were measured there.** It
is a Chinese-language, Chinese-platform measurement. No equivalent public dataset
exists for Israel or Hebrew-language AI answers.

The direction of the finding is almost certainly right everywhere - engines cite
third-party sources far more than vendor sites - but the magnitude must be
measured locally. Build the local source map from the engagement's own sampling:
collect the domains actually cited in the answers to the client's own question
set, rank them by frequency, and let that ranked list drive the external-source
plan. That is a defensible, client-specific number instead of a borrowed one.

## Axis 2 - Risk

Every ticket carries a risk level that governs how the change is deployed.

| Risk | What it covers | Discipline |
|---|---|---|
| **low** | Purely additive: new pages, new blocks, new schema, off-site actions. Nothing existing is modified. | Ship first. Builds trust with the client, reversible at any moment. |
| **observe** | Editing existing pages, adding content to ranking pages. | Do not change URLs. Do not change the core topic of a page that already ranks. Record the before state. Re-check at 7, 14 and 28 days. |
| **high** | robots.txt, WAF/CDN rules, noindex directives, rendering architecture, canonical or URL structure. | Back up the current state first. Schedule separately from content work. Deploy in small batches. Keep a rollback ready. Re-run the audit immediately after deploy. |

### Protective rules that apply to every engagement

- **Protect existing search assets before adding new ones.** Existing URLs,
  canonicals, titles and accumulated authority are the client's property. AI
  visibility work that damages current organic performance is a net loss, no
  matter what the GEO score does.
- **Never bulk-edit a large set of indexed pages at once.** Small batches, with
  the pre-change state recorded per batch, so a regression can be traced to a
  specific batch.
- **When the numbers do not improve, diagnose before continuing.** More of an
  ineffective change is not a strategy.
- **Defensive work counts.** Excluding junk URLs from the sitemap and blocking
  internal search, session and pagination parameters in robots.txt protects the
  entity representation as much as any new content does.
- **Multilingual sites need reciprocal hreflang** before new language content is
  added, or the new pages compete with the existing ones.

## Ticket format

Every ticket must carry: what fails, the layer, the priority, the risk, the owner,
the basis (which reference section justifies it), and a **machine-checkable
acceptance criterion**. Tickets that cannot be machine-checked are typed `manual`
and are never auto-completed.

Use `assets/tickets.template.json` and re-run `scripts/verify_tickets.py` every
cycle. A ticket the checker cannot confirm is not done, whatever the status field
says - and a ticket that stops passing goes back to `regressed` on its own.
