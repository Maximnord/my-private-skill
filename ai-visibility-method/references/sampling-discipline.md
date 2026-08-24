# Sampling and attribution discipline

Visibility numbers are only worth what their collection method is worth. Most GEO
reporting fails here: one platform is sampled, in a logged-in personal account,
with follow-up questions in the same conversation, and the resulting percentage is
presented as "AI visibility". Every one of those choices inflates the number.

These rules exist so a number in a client report can survive being questioned.

---

## Evidence grades

Tag every sample. Never mix grades in one figure.

| Grade | Meaning |
|---|---|
| **A** | Human or browser sample with the full answer text, the cited links, and the recorded environment. |
| **B** | Reproducible API sample, with the web-access state noted (grounded or not). |
| **C** | Synthetic or inferred - illustration only, never a metric. |
| **D** | Needs re-checking. Anything whose environment was not recorded lands here. |

A sample with no answer text, no screenshot or export, and no environment record
is **not** a real sample. Do not label it as one.

## The environment is part of the measurement

| Mode | Grade | When |
|---|---|---|
| `sandbox` | A | Throwaway browser profile, no history, no cookies. Best for engines that do not require login. |
| `incognito` | A | Private window, not logged in. |
| `clean_profile` | A | A dedicated sampling profile: used only for sampling, never searches the client's own brand, memory and personalisation switched off. Required for engines that force a login. |
| `personal` | **D** | A normal personal account measures what the AI thinks *of you*, not what it tells the market. Automatically downgrade. |

Additional rules that change results more than people expect:

- **API is not the web product.** Most vendor APIs answer from parametric memory
  with no retrieval; the consumer product retrieves. They measure different
  things. Record them as separate rows and never average them together.
- **Web is not the app.** The same product on web and in its mobile app can draw
  on materially different source sets. One row per platform *and* surface.
- **A new conversation for every question.** Follow-ups inherit context and bias
  every later answer.
- **Record non-mentions.** "The brand did not appear" is the most important
  datapoint in the set. A sample list containing only the hits is a sales deck.
- **One platform never speaks for "AI".** Never write "AI says X" from one engine.
- **Respect the platforms.** Sampling volume stays modest, terms of service are
  respected, and nothing simulates a login or automates a logged-in account at
  scale. For client work, keep sampling manual or API-based - an automated
  browser queue running through a personal account is a liability that no
  visibility number is worth.

## Metrics: four layers, not one

Mention rate alone always overstates results. Report:

1. **Mention rate** - the brand appears at all.
2. **Position** - first, top three, or an also-ran in a list.
3. **Description accuracy** - is what the answer says about the brand correct?
4. **Citation quality** - is the brand's own material cited, and are the cited
   sources the ones the plan targets?

Split every metric by market and by platform. A cross-market average has no
interpretation.

**Brand-verification questions ("what is <brand>?") are excluded from mention
rate.** They name the brand, so the answer necessarily repeats it. Score them
separately as brand comprehension - they measure accuracy, not visibility.

## Question set structure

Seven groups, three to six questions each: recommendation, comparison,
alternatives, pricing, risk/objection, brand verification, use case.

Group them by intent, because that is what decides where to spend content effort:

- **Buyer intent** - recommendation, comparison, alternatives, pricing. Closest to
  revenue, fix first.
- **Education** - use case, risk. Builds the topical footprint.
- **Probe** - brand verification. Diagnostic only, excluded from visibility rates.

Every question is tagged with its market and language, and written natively in
that language. A translated question is a different question: Hebrew buyers do
not phrase a search the way an English template translates.

## Attribution

Default to **"observed correlation"**. Upgrading to a causal claim requires a
baseline window, an observation window, control prompts, competitor comparison,
and a record of external events in the period.

Reality check for the traffic side: AI referrals frequently arrive without a
referrer - in-app browsers strip it. Whatever is measured is therefore a **lower
bound**. Write "attributable AI sessions >= N", never "AI sent N sessions". AI
traffic is typically low-volume and high-intent, so read conversion rate before
session count. Do not add UTM parameters to publicly cited URLs: a parameterised
URL that gets cited splits citations away from the canonical one.

## What can never be promised

No engine can be guaranteed to cite a given page. GEO changes probability, not
certainty. Put that sentence in the proposal, in those words. Everything that can
honestly be promised is: discoverability, verifiability, extractability, and
correctness of the facts the model repeats.

## Cadence

Technical audit weekly; answer sampling every two to four weeks. Sampling costs
money and the metric is noisy - sampling too often produces movement without
signal. A light weekly check of buyer-intent questions only is a reasonable
middle ground.

## Provenance

Distilled from the GeoLook skill's method layer (MIT, see `ATTRIBUTION.md`), which
sources its figures from two public empirical studies and the CN-GEO citation
dataset. The disciplines above are method, not measurement, and transfer between
markets; the underlying percentages do not. Re-derive any percentage locally
before putting it in a client document.
