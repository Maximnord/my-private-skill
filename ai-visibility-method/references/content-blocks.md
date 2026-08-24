# Content engineering: the citable unit is the passage

Retrieval selects passages, not pages. One self-contained paragraph that answers
the question can beat a competitor's entire page; and a long, well-written page
without a single self-contained passage is never selected at all.

So the unit of work is not "a page about X". It is **an extractable block of fact**.

---

## The quotable-passage test

Applied per section by `scripts/passage_audit.py`. A passage is quotable when it
is long enough to stand alone (60+ words) **and** carries at least one piece of
hard information: a figure, a definition, or a procedural step.

A page with three or more sections and 300+ words but zero quotable passages gets
`NO_QUOTABLE_PASSAGE`. The fix is not more words. Rewrite two or three core
sections so that the opening paragraph directly answers the question posed by its
own heading, and carries a number, a definition or a step list.

## The five blocks

| Block | Weight | What counts |
|---|---:|---|
| Definition | 6 | One sentence that can be lifted whole: what this is, in the reader's words. |
| Figures | 6 | Three or more concrete numbers with units and provenance. |
| Comparison | 5 | An explicit comparison, ideally a table with identical criteria per option. |
| Steps | 5 | An ordered procedure, numbered. |
| FAQ | 3 | Questions in the phrasing users actually use, answers visible in static HTML. |

Reported by `passage_audit.py` as `block_score` out of 25.

Two findings worth internalising, because they contradict common practice:

- **Formatting something as a Q&A does not, by itself, help.** What helps is the
  presence of definitions, figures, comparisons and topical relevance. An FAQ that
  contains no hard information adds nothing.
- **Reference-style pages underperform.** Pages built around a definition or a
  comparison are selected far more often than neutral reference material.

## The evidence-page skeleton

Write evidence pages, not opinion pages. For each target question:

1. Title: the target question in the words a user would actually use.
2. What it is: one liftable definition sentence, then one paragraph of expansion.
3. Key figures: three to five, each with a unit, a source and a date.
4. X versus Y: a table with the same criteria for each option.
5. How to do it: five numbered steps.
6. Where it fits and where it does not. Stating who this is *not* for raises
   trust and is disproportionately quoted.
7. FAQ: three to five real questions.
8. Sources: real, clickable, dated.

## Relevance beats polish

The single strongest predictor of whether a passage is absorbed into an answer is
its relevance to the asked question - stronger than semantic similarity, stronger
than general content quality. Titles, H1 and H2 must contain the actual words of
the target question.

Weak: "The future of customer management".
Strong: "What does a CRM cost for a small business in Israel? 2026 pricing, by tier".

## Duplication works against you

Several URLs answering the same question, or near-duplicate bodies, force
retrieval to choose between your own candidates - and it may choose the weaker
one. Merge them, or canonicalise to a single version. Also keep low-value URLs
(internal search, filters, pagination, session parameters) out of the sitemap and
blocked in robots.txt: they dilute the entity representation.

## Authority signals

A visible publication or update date, a named author, three or more outbound
references, and valid structured data. These mostly decide whether a page is
eligible for the candidate pool at all - not how influential it is once inside.
Authority buys entry; the blocks above win the citation.

---

## Hebrew and bilingual sites

Most GEO tooling silently fails on Hebrew. Verify before trusting any number:

- **Word counting.** Implementations that count `[A-Za-z]` and CJK ranges return
  **zero words** for a Hebrew page, which then cascades into a false "JS-rendered
  empty shell" P0 and false "missing block" findings across the board. This is not
  hypothetical: it is the observed behaviour of the GeoLook auditor and of any
  scorer built the same way. `scripts/passage_audit.py` counts Hebrew, Arabic,
  Cyrillic, Latin and CJK.
- **Block detection needs Hebrew patterns.** English regexes for "X is a",
  "compared to", "step 1" match nothing in Hebrew. The Hebrew pack in
  `passage_audit.py` covers the copula definition form, explicit definition
  markers, comparison, procedure, FAQ, date and author phrasings.
- **The definition form differs.** In English the definitional sentence is "X is
  a Y". Hebrew uses the copula pronoun (hu / hi) in the same position, and that
  pattern is what the Hebrew pack keys on. Write the definition sentence in that
  form deliberately - it is the shape an extractor recognises.
- **Numbers carry local units.** Shekel amounts, VAT, and Israeli-format dates.
  The figure block should use the units the audience uses.
- **RTL markup is an audit item.** Hebrew content without `dir="rtl"` on the root
  element, or with a mismatched `lang` attribute, is flagged. It affects rendering
  and signals the wrong locale to parsers.
- **Bilingual sites need reciprocal hreflang** and genuinely native content on
  both sides. An English page machine-translated into Hebrew reads as translated
  and does not answer the question a Hebrew speaker actually asked. Existing
  skills cover the writing itself: `hebrew-content-writer`,
  `hebrew-seo-geo-toolkit`, `hebrew-rtl-best-practices`.

## Provenance

Thresholds and block weights are distilled from the GeoLook skill's method layer
(MIT, see `ATTRIBUTION.md`), which derives them from two public empirical studies
of AI citation behaviour. Those studies are English and Chinese-language; treat
the weights as a sound ordering of effort, not as calibrated constants for Hebrew.
The Hebrew handling in this skill is original work and is covered by the test
suite in `tests/test_passage.py`.
