#!/usr/bin/env python3
"""Passage-level citability audit with Hebrew, English, Russian and CJK support.

Retrieval selects PASSAGES, not pages: one self-contained paragraph that answers
the question can beat a competitor's whole page, and a long page without a single
quotable passage is never selected at all. This script scores that layer.

Why it exists: the usual implementations count words with `[A-Za-z]` or CJK
ranges only and detect "definition/comparison/how-to" with English regexes. On a
Hebrew page that yields word_count = 0, a false "JS-rendered empty shell" P0 and
five false "missing block" findings - a confidently wrong audit. Every pattern
here is per-language, and word counting is script-aware.

Usage:
    passage_audit.py <url|file.html> [--lang he|en|auto] [--json]
    passage_audit.py --text "raw text ..." [--lang he]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetchlib import BROWSER_UA, fetch  # noqa: E402

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    print("ERROR: pip install beautifulsoup4 lxml", file=sys.stderr)
    raise SystemExit(2)

# ---------------------------------------------------------------- scripts

HEBREW = re.compile(r"[֐-׿]")
ARABIC = re.compile(r"[؀-ۿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
CJK = re.compile(r"[一-鿿぀-ヿ가-힯]")
LATIN = re.compile(r"[A-Za-z]")

# A word starts with a letter from any space-delimited script we support.
WORD = re.compile(r"[A-Za-zЀ-ӿ֐-׿؀-ۿ]"
                  r"[A-Za-z0-9Ѐ-ӿ֐-׿؀-ۿ'’׳״\-]*")


def word_count(text: str) -> int:
    """Script-aware word count. Space-delimited scripts are tokenised; CJK is
    converted at 1.6 characters per word to keep thresholds comparable."""
    return len(WORD.findall(text)) + int(len(CJK.findall(text)) / 1.6)


def detect_lang(text: str) -> str:
    sample = text[:20000]
    counts = {"he": len(HEBREW.findall(sample)), "ar": len(ARABIC.findall(sample)),
              "ru": len(CYRILLIC.findall(sample)), "zh": len(CJK.findall(sample)),
              "en": len(LATIN.findall(sample))}
    total = sum(counts.values()) or 1
    # Hebrew/Arabic/Cyrillic pages carry a lot of Latin (brands, tech terms), so a
    # minority share still means the page is written in that language.
    for code in ("he", "ar", "ru", "zh"):
        if counts[code] / total > 0.15:
            return code
    return "en"


# ---------------------------------------------------------------- patterns

NUMBER_GENERIC = re.compile(
    r"(\d[\d,.]*\s?(%|percent|₪|\$|€|£|ש\"ח|שקל|אחוז|km|kg|mb|gb|nis|ils|hours?|days?|years?|months?|users?"
    r"|שעות|ימים|שנים|חודשים|מ\"ר|ק\"מ|руб|₽)|\b\d{4}\b|\d+[\d,.]*\s*(x|×)\s*\d)", re.I)

PACKS = {
    "en": {
        "definition": re.compile(
            r"(\b\w+\s+is\s+(?:a|an|the)\b|\brefers?\s+to\b|\bis\s+defined\s+as\b|"
            r"\bmeans\s+that\b|\bstands\s+for\b|\bin\s+other\s+words\b|\bwhat\s+is\b)", re.I),
        "comparison": re.compile(
            r"(\bvs\.?\b|\bversus\b|\bcompared\s+to\b|\bdifference\s+between\b|"
            r"\balternatives?\s+to\b|\bpros\s+and\s+cons\b|\bbetter\s+than\b)", re.I),
        "howto": re.compile(
            r"(\bstep\s*\d|\bstep\s+(one|two|three)\b|\bhow\s+to\b|\bstep[-\s]by[-\s]step\b|"
            r"\bfollow\s+these\s+steps\b)", re.I),
        "faq": re.compile(r"(\bFAQ\b|frequently\s+asked|^\s*Q[:.]\s|^\s*A[:.]\s)", re.I | re.M),
        "date": re.compile(r"(\bupdated\b|\blast\s+updated\b|\bpublished\b|\bas\s+of\s+20\d{2})", re.I),
        "author": re.compile(r"(\bauthor\b|\bwritten\s+by\b|\bby\s+[A-Z][a-z]+\s+[A-Z][a-z]+)"),
    },
    "he": {
        # A copula sentence ("X hu/hi ...") is the Hebrew definition form; the
        # explicit markers below catch the rest.
        "definition": re.compile(
            # Hebrew subjects are routinely multi-word ("Max Soskind Studio hu ..."),
            # so allow up to four tokens between the sentence start and the copula.
            r"((?:^|[.!?]\s|\n)\s*(?:\S+\s+){1,4}(?:הוא|היא|הם|הן)\s+\S+|מוגדר(?:ת|ים|ות)?\s+כ|"
            r"כלומר|מדובר\s+ב|הכוונה\s+ל|נקרא(?:ת|ים|ות)?\s|מה\s+ז[הו]\b|מהו\b|מהי\b|"
            r"הידוע(?:ה)?\s+גם\s+כ|בשפה\s+פשוטה)"),
        "comparison": re.compile(
            r"(לעומת|בהשוואה\s+ל|ההבדל(?:ים)?\s+בין|הבדלים\s+בין|יתרונות\s+וחסרונות|"
            r"חלופ(?:ה|ות)|אלטרנטיב|מה\s+עדיף|למי\s+מתאים|מול\s+\S+\s*:)"),
        "howto": re.compile(
            r"(שלב\s*\d|שלב\s+(?:ראשון|שני|שלישי|רביעי)|צעד\s+אחר\s+צעד|כיצד\s|"
            r"איך\s+ל|מדריך\b|אופן\s+ה?שימוש|תהליך\s+ה?עבודה)"),
        "faq": re.compile(r"(שאלות\s+נפוצות|שאלות\s+ותשובות|^\s*ש[:.]\s|^\s*ת[:.]\s)", re.M),
        "date": re.compile(r"(עודכן|עדכון\s+אחרון|פורסם\s+ב|נכון\s+ל|תאריך\s+עדכון)"),
        "author": re.compile(r"(מאת\b|נכתב\s+על\s+ידי|כתב(?:ה)?:|עורך\s+ה?תוכן)"),
    },
    "ru": {
        "definition": re.compile(
            r"(\bэто\s+\w+|\bявляется\b|\bназывается\b|\bопредел[её]н\w*\s+как\b|"
            r"\bиными\s+словами\b|\bчто\s+такое\b)", re.I),
        "comparison": re.compile(r"(\bпротив\b|\bпо\s+сравнению\b|\bотличи[ея]\b|\bразница\s+между\b|"
                                 r"\bальтернатив\w*|\bплюсы\s+и\s+минусы\b|\bvs\.?\b)", re.I),
        "howto": re.compile(r"(\bшаг\s*\d|\bкак\s+\w+ть\b|\bпошагов\w*|\bинструкция\b)", re.I),
        "faq": re.compile(r"(частые\s+вопросы|вопросы\s+и\s+ответы|\bFAQ\b)", re.I),
        "date": re.compile(r"(обновлено|опубликовано|дата\s+обновления)", re.I),
        "author": re.compile(r"(\bавтор\b|\bнаписал\w*\b)", re.I),
    },
}
PACKS["ar"] = PACKS["en"]   # placeholder: Arabic pages fall back to script-aware counting
PACKS["zh"] = PACKS["en"]

BLOCK_WEIGHTS = {"definition": 6, "numbers": 6, "comparison": 5, "howto": 5, "faq": 3}
QUOTABLE_MIN_WORDS = 60


def pack_for(lang: str) -> dict:
    return PACKS.get(lang, PACKS["en"])


# ---------------------------------------------------------------- extraction

# Removed everywhere: chrome that never carries body content.
def jsonld_types(node, depth: int = 0) -> list[str]:
    """Collect @type values, walking @graph and nested entities.

    Yoast, RankMath and most WordPress SEO plugins emit one script containing an
    @graph array. Readers that only look at the top level report "no structured
    data" on sites that are in fact fully marked up."""
    if depth > 6:
        return []
    found: list[str] = []
    if isinstance(node, list):
        for item in node:
            found.extend(jsonld_types(item, depth + 1))
        return found
    if not isinstance(node, dict):
        return found
    t = node.get("@type")
    if t:
        found.extend(t if isinstance(t, list) else [t])
    for key in ("@graph", "mainEntity", "itemListElement", "about", "hasPart", "author",
                "publisher", "provider", "makesOffer", "subjectOf"):
        if key in node:
            found.extend(jsonld_types(node[key], depth + 1))
    return found


STRIP_ALWAYS = ("script", "style", "noscript", "nav", "aside", "form", "svg", "iframe")
# <header>/<footer> are ALSO the HTML5 wrappers for section headings inside
# <section>/<article>. Stripping them blindly deletes most of a themed page's H2s
# and collapses the whole body into one giant unsectioned blob.
STRIP_IF_PAGE_CHROME = ("header", "footer")


def sections_from_html(html: str) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    meta = {
        "title": (soup.title.get_text(strip=True) if soup.title else ""),
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")],
        "lang_attr": (soup.html.get("lang") if soup.html else "") or "",
        "dir_attr": (soup.html.get("dir") if soup.html else "") or "",
        "jsonld_types": [],
    }
    for tag in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:  # noqa: BLE001
            continue
        meta["jsonld_types"].extend(jsonld_types(data))

    body = soup.body or soup
    for tag in body.find_all(STRIP_ALWAYS):
        tag.decompose()
    for tag in body.find_all(STRIP_IF_PAGE_CHROME):
        # Site chrome sits outside the content containers; a section header sits inside one.
        if tag.find_parent(["article", "section", "main"]) is None:
            tag.decompose()

    sections: list[dict] = []
    current = {"heading": "(intro)", "text": "", "list_items": 0}
    for el in body.find_all(["h2", "h3", "p", "li", "td", "th", "div"]):
        if el.name == "h2":
            sections.append(current)
            current = {"heading": el.get_text(" ", strip=True), "text": "", "list_items": 0}
            continue
        if el.name == "div" and el.find(["p", "li", "h2", "h3", "div"]):
            continue  # container: its children are visited separately
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name == "li":
            current["list_items"] += 1
        current["text"] += txt + "\n"
    sections.append(current)
    return [s for s in sections if s["text"].strip() or s["heading"] != "(intro)"], meta


def audit_text(text: str, lang: str) -> dict:
    pk = pack_for(lang)
    return {
        "definition": bool(pk["definition"].search(text)),
        "numbers": len(NUMBER_GENERIC.findall(text)) >= 3,
        "comparison": bool(pk["comparison"].search(text)),
        "howto": bool(pk["howto"].search(text)),
        "faq": bool(pk["faq"].search(text)),
    }


def comparison_table(html: str) -> bool:
    """Whether the page carries a comparison laid out as a table.

    The textual patterns above look for "vs", "compared to", "לעומת" and their
    kin. A page can state a comparison perfectly well without any of those: a
    table with one row per criterion and one column per option is the canonical
    form, and content-blocks.md names it as the preferred one. Detecting only
    the prose form reports a real comparison table as a missing block, which is
    what happened on this site's home pages.

    Deliberately strict, so an ordinary data table does not qualify: at least
    two data rows, at least three columns (the criterion plus two options being
    compared), and a header of some kind - either a row header per row, or a
    header row naming the options. Structure-based, so it works identically on
    Hebrew, Arabic and every other script.
    """
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        data_rows = [r for r in rows if r.find_all("td")]
        if len(data_rows) < 2:
            continue
        widest = max(len(r.find_all(["td", "th"])) for r in data_rows)
        if widest < 3:
            continue
        row_headers = sum(1 for r in data_rows if r.find("th"))
        header_row = any(r.find_all("th") and not r.find_all("td") for r in rows)
        if row_headers >= 2 or header_row:
            return True
    return False


def is_quotable(text: str, lang: str) -> tuple[bool, str]:
    """A passage is quotable when it can stand alone in an answer: enough
    substance, plus at least one piece of hard information."""
    wc = word_count(text)
    if wc < QUOTABLE_MIN_WORDS:
        return False, f"too short ({wc} words, need {QUOTABLE_MIN_WORDS})"
    pk = pack_for(lang)
    if NUMBER_GENERIC.search(text):
        return True, "contains concrete figures"
    if pk["definition"].search(text):
        return True, "contains a definition"
    if pk["howto"].search(text):
        return True, "contains procedural steps"
    return False, "no hard information (no figures, definition or steps)"


def audit(html: str, lang: str = "auto", url: str = "") -> dict:
    sections, meta = sections_from_html(html)
    full_text = "\n".join(s["heading"] + "\n" + s["text"] for s in sections)
    resolved = detect_lang(full_text) if lang == "auto" else lang
    total_words = word_count(full_text)

    scored = []
    for s in sections:
        body_text = s["heading"] + "\n" + s["text"]
        ok, why = is_quotable(body_text, resolved)
        scored.append({"heading": s["heading"][:120], "words": word_count(body_text),
                       "list_items": s["list_items"], "quotable": ok, "reason": why})

    blocks = audit_text(full_text, resolved)
    # A comparison can be stated in prose or laid out as a table; audit_text()
    # only sees the prose, so the structural form is added here where the HTML
    # is still in scope.
    blocks["comparison"] = blocks["comparison"] or comparison_table(html)
    block_score = sum(w for k, w in BLOCK_WEIGHTS.items() if blocks[k])
    pk = pack_for(resolved)
    quotable = sum(1 for s in scored if s["quotable"])

    issues = []
    if total_words < 120:
        issues.append({"code": "EMPTY_SHELL", "severity": "P0",
                       "text": "Static HTML contains almost no body text. Most AI crawlers do not "
                               "execute JavaScript, so they see a blank page. Verify with "
                               "ai_ua_probe.py before reporting - a WAF stub looks identical."})
    elif total_words < 1000:
        issues.append({"code": "SHORT_CONTENT", "severity": "P1",
                       "text": f"{total_words} words. 1,000 is the threshold below which pages are "
                               f"rarely selected as a source, not a target to aim at."})
    if quotable == 0 and len(scored) >= 3 and total_words >= 300:
        issues.append({"code": "NO_QUOTABLE_PASSAGE", "severity": "P1",
                       "text": "Not one section can be quoted on its own. Rewrite 2-3 core sections "
                               "so the first paragraph directly answers the section heading and "
                               "carries a figure, a definition or a step list."})
    for name, present in blocks.items():
        if not present:
            issues.append({"code": f"NO_{name.upper()}", "severity": "P1",
                           "text": f"No '{name}' block detected ({resolved} patterns)."})
    if not pk["date"].search(full_text):
        issues.append({"code": "NO_DATE", "severity": "P2",
                       "text": "No visible publication or update date."})
    if not pk["author"].search(full_text):
        issues.append({"code": "NO_AUTHOR", "severity": "P2", "text": "No visible author attribution."})
    if resolved == "he" and meta["dir_attr"].lower() != "rtl":
        issues.append({"code": "MISSING_DIR_RTL", "severity": "P2",
                       "text": "Hebrew content without dir=\"rtl\" on <html>. Hurts rendering and "
                               "signals the wrong locale to parsers."})
    if resolved != "en" and meta["lang_attr"][:2].lower() not in (resolved, ""):
        issues.append({"code": "LANG_ATTR_MISMATCH", "severity": "P2",
                       "text": f"Content reads as '{resolved}' but <html lang> is "
                               f"'{meta['lang_attr'] or 'unset'}'."})

    return {
        "url": url, "language_detected": resolved, "meta": meta,
        "word_count": total_words, "sections_total": len(scored),
        "sections_quotable": quotable, "sections": scored,
        "blocks": blocks, "block_score": block_score, "block_score_max": sum(BLOCK_WEIGHTS.values()),
        "issues": issues,
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    lang = "auto"
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            lang = argv[i + 1]

    if argv[0] == "--text":
        text = argv[1]
        html = "<html><body><p>" + text.replace("\n", "</p><p>") + "</p></body></html>"
        data = audit(html, lang)
    else:
        target = argv[0]
        p = Path(target)
        if p.exists():
            data = audit(p.read_text("utf-8", errors="replace"), lang, str(p))
        else:
            res = fetch(target, BROWSER_UA)
            if res.error or res.status != 200:
                print(f"fetch failed: HTTP {res.status} {res.error}", file=sys.stderr)
                return 2
            data = audit(res.text, lang, target)

    if "--json" in argv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"{data['url'] or '(text)'}")
    print(f"  language: {data['language_detected']}   words: {data['word_count']}   "
          f"blocks: {data['block_score']}/{data['block_score_max']}")
    print(f"  quotable passages: {data['sections_quotable']}/{data['sections_total']}")
    print("\n  sections")
    for s in data["sections"]:
        mark = "QUOTE" if s["quotable"] else "  -  "
        print(f"   [{mark}] {s['words']:>4}w  {s['heading'][:60]:<60} {s['reason']}")
    print("\n  findings")
    for i in data["issues"]:
        print(f"   {i['severity']}  {i['code']}: {i['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
