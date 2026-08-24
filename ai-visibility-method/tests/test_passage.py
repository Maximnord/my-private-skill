import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import passage_audit as P

HE_PARA = ("אקמה היא חברת תוכנה ישראלית המספקת פתרונות ניהול לקוחות לעסקים קטנים ובינוניים. "
           "המערכת כוללת ניהול לידים, אוטומציה שיווקית ודוחות בזמן אמת. "
           "המחיר מתחיל ב-149 ש\"ח לחודש למשתמש והתמיכה ניתנת בעברית ובאנגלית. ")


def he_page(extra: str = "", lang: str = "he", direction: str = "rtl") -> str:
    secs = "".join(
        f"<h2>סעיף {i}</h2>" + "".join(f"<p>{HE_PARA}</p>" for _ in range(4))
        for i in range(1, 5))
    return (f'<html lang="{lang}" dir="{direction}"><head><title>אקמה</title></head>'
            f"<body><h1>אקמה</h1>{secs}{extra}</body></html>")


class WordCounting(unittest.TestCase):
    def test_hebrew_words_are_counted(self):
        self.assertGreater(P.word_count(HE_PARA), 25)

    def test_cyrillic_and_arabic_counted(self):
        self.assertGreater(P.word_count("Российская компания предоставляет решения"), 3)
        self.assertGreater(P.word_count("شركة إسرائيلية تقدم حلولا"), 3)

    def test_latin_and_cjk_still_work(self):
        self.assertEqual(P.word_count("one two three"), 3)
        self.assertGreater(P.word_count("这是一个中文页面的正文内容示例" * 3), 10)

    def test_mixed_hebrew_and_latin(self):
        self.assertGreater(P.word_count("מערכת CRM לעסקים בישראל"), 3)


class LanguageDetection(unittest.TestCase):
    def test_hebrew_page_with_latin_brand_names(self):
        self.assertEqual(P.detect_lang(HE_PARA + " Acme CRM SaaS platform"), "he")

    def test_english(self):
        self.assertEqual(P.detect_lang("A plain English paragraph about software."), "en")


class HebrewPageIsNotMisdiagnosed(unittest.TestCase):
    """The regression this skill exists to prevent: a static Hebrew page read as
    an empty JS shell with zero extractable blocks."""

    def setUp(self):
        self.data = P.audit(he_page(), "auto")

    def test_language_and_word_count(self):
        self.assertEqual(self.data["language_detected"], "he")
        self.assertGreater(self.data["word_count"], 400)

    def test_no_false_empty_shell(self):
        codes = [i["code"] for i in self.data["issues"]]
        self.assertNotIn("EMPTY_SHELL", codes)

    def test_hebrew_blocks_are_detected(self):
        self.assertTrue(self.data["blocks"]["definition"])
        self.assertTrue(self.data["blocks"]["numbers"])

    def test_quotable_passages_found(self):
        self.assertGreaterEqual(self.data["sections_quotable"], 3)


class HebrewPatternPacks(unittest.TestCase):
    def test_comparison(self):
        d = P.audit(he_page("<p>" + HE_PARA + " ההבדלים בין המערכות ואלטרנטיבות בשוק.</p>"), "he")
        self.assertTrue(d["blocks"]["comparison"])

    def test_howto_and_faq(self):
        d = P.audit(he_page("<h2>שאלות נפוצות</h2><p>שלב 1: הרשמה. שלב 2: ייבוא.</p>"), "he")
        self.assertTrue(d["blocks"]["faq"])
        self.assertTrue(d["blocks"]["howto"])

    def test_date_and_author_do_not_fire_falsely(self):
        d = P.audit(he_page(), "he")
        codes = [i["code"] for i in d["issues"]]
        self.assertIn("NO_DATE", codes)
        self.assertIn("NO_AUTHOR", codes)
        d2 = P.audit(he_page("<p>עודכן: 2026-08-01 | מאת דנה לוי</p>"), "he")
        codes2 = [i["code"] for i in d2["issues"]]
        self.assertNotIn("NO_DATE", codes2)
        self.assertNotIn("NO_AUTHOR", codes2)


class MultiWordSubjectCopula(unittest.TestCase):
    """Real sentence from a live Hebrew page. A one-token-subject pattern misses it
    and reports a false "no definition block" on a page that opens with one."""

    REAL = ("מקס סוסקינד הוא סטודיו בהובלת המייסד, שבונה ומקדם אתרים לעסקים "
            "וחברות בישראל ובעולם. תהליך שקוף, מובנה ומדויק לכל שלב.")

    def test_multi_word_subject_is_a_definition(self):
        self.assertTrue(P.PACKS["he"]["definition"].search(self.REAL))

    def test_single_word_subject_still_matches(self):
        self.assertTrue(P.PACKS["he"]["definition"].search("אקמה היא חברת תוכנה ישראלית."))

    def test_mid_sentence_pronoun_is_not_a_definition(self):
        prose = ("כאשר הלקוח פונה אלינו ואנחנו בודקים את האתר שלו לעומק ומגלים בעיות רבות "
                 "מאוד שדורשות טיפול הוא מקבל דוח מפורט")
        self.assertFalse(P.PACKS["he"]["definition"].search(prose))


class RtlAndLangAttributes(unittest.TestCase):
    def test_missing_dir_rtl_is_flagged(self):
        d = P.audit(he_page(direction=""), "he")
        self.assertIn("MISSING_DIR_RTL", [i["code"] for i in d["issues"]])

    def test_lang_attr_mismatch(self):
        d = P.audit(he_page(lang="en"), "he")
        self.assertIn("LANG_ATTR_MISMATCH", [i["code"] for i in d["issues"]])


class ShellDetectionStillWorks(unittest.TestCase):
    def test_real_spa_shell(self):
        d = P.audit('<html lang="he" dir="rtl"><body><div id="root"></div></body></html>', "auto")
        self.assertIn("EMPTY_SHELL", [i["code"] for i in d["issues"]])

    def test_long_page_without_hard_information(self):
        filler = "<p>" + ("אנחנו מאמינים בשירות מצוין ובחוויית לקוח יוצאת דופן עבור כל אחד. " * 10) + "</p>"
        d = P.audit(f'<html lang="he" dir="rtl"><body>' +
                    "".join(f"<h2>חלק {i}</h2>{filler}" for i in range(1, 5)) + "</body></html>", "he")
        self.assertEqual(d["sections_quotable"], 0)
        self.assertIn("NO_QUOTABLE_PASSAGE", [i["code"] for i in d["issues"]])


class SectionHeadersSurviveStripping(unittest.TestCase):
    """HTML5 uses <header> both for site chrome and for section headings. Stripping
    it blindly deletes the H2s and collapses the page into one unsectioned blob."""

    HTML = ('<html lang="en"><body>'
            '<header id="site"><nav><a href="/">home</a></nav><h2>Site chrome heading</h2></header>'
            '<main>'
            '<section><header><h2>Real section one</h2></header><p>' + ("word " * 80) + '2026 figures</p></section>'
            '<section><header><h2>Real section two</h2></header><p>' + ("word " * 80) + '149 NIS</p></section>'
            '</main>'
            '<footer><h2>Footer heading</h2><p>contact</p></footer></body></html>')

    def setUp(self):
        self.data = P.audit(self.HTML, "en")

    def test_section_headings_are_kept(self):
        headings = [s["heading"] for s in self.data["sections"]]
        self.assertIn("Real section one", headings)
        self.assertIn("Real section two", headings)

    def test_page_chrome_is_dropped(self):
        headings = [s["heading"] for s in self.data["sections"]]
        self.assertNotIn("Site chrome heading", headings)
        self.assertNotIn("Footer heading", headings)

    def test_content_is_not_collapsed_into_one_blob(self):
        self.assertGreaterEqual(self.data["sections_total"], 2)


class Metadata(unittest.TestCase):
    def test_jsonld_types_collected(self):
        html = ('<html lang="en"><body><script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"Organization","name":"A"}</script>'
                "<p>text</p></body></html>")
        self.assertIn("Organization", P.audit(html, "en")["meta"]["jsonld_types"])

    def test_yoast_style_graph_is_unwrapped(self):
        html = ('<html lang="en"><body><script type="application/ld+json">'
                '{"@context":"https://schema.org","@graph":['
                '{"@type":"WebPage"},{"@type":"BreadcrumbList"},'
                '{"@type":["LocalBusiness","Organization"],"name":"Studio"},'
                '{"@type":"Review"}]}</script><p>text</p></body></html>')
        types = P.audit(html, "en")["meta"]["jsonld_types"]
        self.assertIn("Organization", types)
        self.assertIn("LocalBusiness", types)
        self.assertIn("BreadcrumbList", types)

    def test_nested_entities_are_reached(self):
        html = ('<html lang="en"><body><script type="application/ld+json">'
                '{"@type":"Article","author":{"@type":"Person","name":"A"}}</script>'
                "<p>text</p></body></html>")
        self.assertIn("Person", P.audit(html, "en")["meta"]["jsonld_types"])

    def test_malformed_jsonld_does_not_crash(self):
        html = '<html><body><script type="application/ld+json">{broken</script><p>x</p></body></html>'
        self.assertEqual(P.audit(html, "en")["meta"]["jsonld_types"], [])



class ComparisonTable(unittest.TestCase):
    """A comparison stated as a table, with no 'vs' anywhere in the copy.

    The prose patterns cannot see this shape, and content-blocks.md names the
    table as the preferred form of a comparison, so missing it reports a real
    block as absent.
    """

    TABLE = ("<table><thead><tr><th>Criterion</th><th>Typical agency</th>"
             "<th>This studio</th></tr></thead><tbody>"
             "<tr><th>Build method</th><td>Page builders</td><td>Hand-coded</td></tr>"
             "<tr><th>Performance</th><td>Bloated output</td><td>Lean code</td></tr>"
             "</tbody></table>")

    def _page(self, body, lang="en"):
        return f'<html lang="{lang}"><body><h1>T</h1>{body}</body></html>'

    def test_table_counts_as_comparison(self):
        self.assertTrue(P.audit(self._page(self.TABLE), "en")["blocks"]["comparison"])

    def test_table_counts_in_hebrew_without_any_marker_word(self):
        he = ("<table><tbody>"
              "<tr><th>שיטת בנייה</th><td>הרכבה בבילדרים</td><td>קוד ידני</td></tr>"
              "<tr><th>ביצועים</th><td>קוד מנופח</td><td>קוד רזה</td></tr>"
              "</tbody></table>")
        self.assertTrue(P.audit(self._page(he, "he"), "he")["blocks"]["comparison"])

    def test_two_column_table_is_not_a_comparison(self):
        two = ("<table><tbody><tr><th>Name</th><td>Alpha</td></tr>"
               "<tr><th>Name</th><td>Beta</td></tr></tbody></table>")
        self.assertFalse(P.audit(self._page(two), "en")["blocks"]["comparison"])

    def test_single_row_table_is_not_a_comparison(self):
        one = ("<table><tbody><tr><th>A</th><td>b</td><td>c</td></tr></tbody></table>")
        self.assertFalse(P.audit(self._page(one), "en")["blocks"]["comparison"])

    def test_prose_comparison_still_detected(self):
        prose = "<p>Our approach compared to a typical agency is different.</p>"
        self.assertTrue(P.audit(self._page(prose), "en")["blocks"]["comparison"])


if __name__ == "__main__":
    unittest.main()
