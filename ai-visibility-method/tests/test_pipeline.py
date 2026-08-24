import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import llmstxt_verify as L
import verify_tickets as V
from ai_ua_probe import classify
from fetchlib import Fetched


class LlmsTxtParsing(unittest.TestCase):
    TXT = ("# Acme\n\n> CRM for Israeli SMBs.\n\n## Docs\n"
           "- [Pricing](/pricing): plans\n- [Guide](https://acme.co.il/guide): onboarding\n")

    def test_structure_and_link_resolution(self):
        d = L.parse_llms_txt(self.TXT, "https://acme.co.il")
        self.assertEqual(d["title"], "Acme")
        self.assertEqual(d["summary"], "CRM for Israeli SMBs.")
        self.assertEqual(d["sections"], ["Docs"])
        self.assertEqual([l["url"] for l in d["links"]],
                         ["https://acme.co.il/pricing", "https://acme.co.il/guide"])

    def test_links_carry_their_section(self):
        d = L.parse_llms_txt(self.TXT, "https://acme.co.il")
        self.assertTrue(all(l["section"] == "Docs" for l in d["links"]))

    def test_empty_file_yields_nothing(self):
        d = L.parse_llms_txt("", "https://acme.co.il")
        self.assertEqual(d["links"], [])
        self.assertEqual(d["title"], "")


class RateLimitIsNotAbsence(unittest.TestCase):
    """A 429 means "ask again later", not "the file does not exist". Reporting a
    missing llms.txt because the server throttled the audit is a false finding."""

    def test_429_is_inconclusive(self):
        import unittest.mock as mock
        with mock.patch.object(L, "fetch", return_value=Fetched(url="u", ua_name="b", status=429)):
            out = L.verify("https://example.co.il")
        self.assertIsNone(out["exists"])
        self.assertIn("INCONCLUSIVE", out["verdict"])

    def test_404_is_absence(self):
        import unittest.mock as mock
        with mock.patch.object(L, "fetch", return_value=Fetched(url="u", ua_name="b", status=404)):
            out = L.verify("https://example.co.il")
        self.assertFalse(out["exists"])
        self.assertIn("no llms.txt", out["verdict"])


class UaProbeClassification(unittest.TestCase):
    def base(self, **kw):
        return Fetched(url="u", ua_name="browser", status=200, length=50000,
                       text="<html>real page</html>", **kw)

    def test_403_is_blocked(self):
        s, _ = classify(self.base(), Fetched(url="u", ua_name="GPTBot", status=403, length=900))
        self.assertEqual(s, "BLOCKED")

    def test_challenge_page_is_caught_despite_http_200(self):
        probe = Fetched(url="u", ua_name="GPTBot", status=200, length=4000,
                        text="<html><title>Just a moment...</title>cf-browser-verification</html>")
        s, _ = classify(self.base(), probe)
        self.assertEqual(s, "CHALLENGED")

    def test_thin_body_is_flagged(self):
        s, _ = classify(self.base(), Fetched(url="u", ua_name="GPTBot", status=200, length=1000))
        self.assertEqual(s, "THIN")

    def test_healthy_fetch_is_ok(self):
        s, _ = classify(self.base(), Fetched(url="u", ua_name="GPTBot", status=200,
                                             length=49000, text="<html>real page</html>"))
        self.assertEqual(s, "OK")

    def test_transport_error_is_not_silently_ok(self):
        s, _ = classify(self.base(), Fetched(url="u", ua_name="GPTBot", error="Timeout"))
        self.assertEqual(s, "ERROR")


class CacheAttribution(unittest.TestCase):
    """A 200 from a page cache says nothing about how the origin answers crawlers."""

    def test_litespeed_hit_is_reported_as_cache(self):
        from ai_ua_probe import cache_state
        r = Fetched(url="u", ua_name="b", status=200, headers={"x-litespeed-cache": "hit"})
        self.assertEqual(cache_state(r), "litespeed:hit")

    def test_cloudflare_dynamic_is_origin(self):
        from ai_ua_probe import cache_state
        r = Fetched(url="u", ua_name="b", status=200, headers={"cf-cache-status": "DYNAMIC"})
        self.assertEqual(cache_state(r), "origin")

    def test_no_cache_headers_is_origin(self):
        from ai_ua_probe import cache_state
        self.assertEqual(cache_state(Fetched(url="u", ua_name="b", status=200)), "origin")


class TicketTransitions(unittest.TestCase):
    def test_pass_completes(self):
        self.assertEqual(V.transition("todo", "PASS"), "done")
        self.assertEqual(V.transition("doing", "PASS"), "done")
        self.assertEqual(V.transition("regressed", "PASS"), "done")

    def test_fail_on_done_is_a_regression(self):
        self.assertEqual(V.transition("done", "FAIL"), "regressed")

    def test_fail_keeps_open_tickets_open(self):
        self.assertEqual(V.transition("todo", "FAIL"), "todo")
        self.assertEqual(V.transition("doing", "FAIL"), "doing")

    def test_manual_and_error_never_move_state(self):
        for state in ("todo", "doing", "done", "regressed"):
            self.assertEqual(V.transition(state, "MANUAL"), state)
            self.assertEqual(V.transition(state, "ERROR"), state)


class TicketRunner(unittest.TestCase):
    def test_manual_check_reports_note_and_holds_status(self):
        result, detail = V.run_check({"type": "manual", "params": {"note": "confirm listing"}})
        self.assertEqual(result, "MANUAL")
        self.assertIn("confirm listing", detail)

    def test_unknown_check_type_is_an_error_not_a_pass(self):
        result, _ = V.run_check({"type": "nonsense", "params": {}})
        self.assertEqual(result, "ERROR")

    def test_broken_check_does_not_abort_the_cycle(self):
        result, detail = V.run_check({"type": "http_status", "params": {}})  # missing url
        self.assertEqual(result, "ERROR")
        self.assertIn("KeyError", detail)

    def test_dry_run_does_not_write_and_write_persists(self):
        doc = {"project": "t", "tickets": [
            {"id": "T-001", "title": "manual one", "status": "todo",
             "check": {"type": "manual", "params": {"note": "n"}}},
            {"id": "T-002", "title": "bad check", "status": "done",
             "check": {"type": "nonsense", "params": {}}},
        ]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tickets.json"
            p.write_text(json.dumps(doc), "utf-8")
            out = V.verify(p, write=False)
            self.assertEqual(json.loads(p.read_text("utf-8"))["tickets"][0]["status"], "todo")
            self.assertEqual(out["summary"]["manual"], 1)
            self.assertEqual(out["summary"]["errors"], 1)
            V.verify(p, write=True)
            saved = json.loads(p.read_text("utf-8"))
            self.assertTrue(saved["updated"])
            self.assertEqual(saved["tickets"][1]["status"], "done")  # ERROR must not demote

    def test_only_filter_limits_the_run(self):
        doc = {"tickets": [
            {"id": "T-001", "status": "todo", "check": {"type": "manual", "params": {}}},
            {"id": "T-002", "status": "todo", "check": {"type": "manual", "params": {}}},
        ]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.json"
            p.write_text(json.dumps(doc), "utf-8")
            self.assertEqual(V.verify(p, only="T-002")["summary"]["checked"], 1)


class ShippedTemplate(unittest.TestCase):
    def test_template_is_valid_and_every_check_type_is_supported(self):
        path = Path(__file__).resolve().parent.parent / "assets" / "tickets.template.json"
        doc = json.loads(path.read_text("utf-8"))
        supported = {"robots_allows", "ua_probe", "http_status", "has_jsonld", "min_words",
                     "has_block", "quotable_passages", "llmstxt_valid", "contains", "manual"}
        for t in doc["tickets"]:
            self.assertIn(t["check"]["type"], supported, t["id"])
            for key in ("id", "title", "layer", "priority", "risk", "basis", "acceptance", "status"):
                self.assertIn(key, t, t["id"])
            self.assertIn(t["layer"], {"access", "targeting", "understanding", "citability"})
            self.assertIn(t["risk"], {"low", "observe", "high"})


if __name__ == "__main__":
    unittest.main()
