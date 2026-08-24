# Attribution

The method layer of this skill is distilled from **GeoLook**
(https://github.com/aigclink/geolook), MIT licensed, Copyright (c) 2026 GeoLook
contributors - specifically its `references/method.md`: the four-layer dependency
model, the priority ordering, the independent risk axis, the sampling and
attribution discipline, the quotable-passage criterion and the extractable-block
weights.

GeoLook in turn sources its figures from two public empirical studies of AI
citation behaviour and the CN-GEO citation dataset (187,818 deduplicated
citations); see that repository's `references/sources.md`.

No GeoLook code was copied. Every script here was written independently from the
described method, and the parts GeoLook gets wrong were deliberately not carried
over:

- GeoLook's word counter recognises CJK and Latin only, so Hebrew, Arabic and
  Cyrillic pages count as zero words. Verified on a static 1,438-word Hebrew page:
  it reported 10 words, a false P0 "JS-rendered empty shell", zero of five
  extractable blocks, and a grade of D. `scripts/passage_audit.py` is
  script-aware and language-packed; `tests/test_passage.py` locks that behaviour.
- Its China-specific source ranking, platform adapters and the 1.37% own-site
  citation share are market-bound measurements and are referenced only as
  provenance, never as rules for other markets.
- Its browser extension's automated queue mode drives logged-in accounts on the
  AI products. Deliberately not reproduced; see `references/sampling-discipline.md`.

The four-layer framing that GeoLook uses is itself credited there to the GEO
Readiness Manual.
