import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import robots_rfc9309 as R


class SharedGroups(unittest.TestCase):
    TXT = "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n"

    def test_rules_bind_to_every_agent_in_the_group(self):
        ev = R.evaluate(self.TXT, ["GPTBot", "ClaudeBot"])
        self.assertEqual(ev["bots"]["GPTBot"]["status"], "BLOCKED")
        self.assertEqual(ev["bots"]["ClaudeBot"]["status"], "BLOCKED")

    def test_trap_is_reported(self):
        ev = R.evaluate(self.TXT, ["GPTBot"])
        self.assertIn("SHARED_GROUP", [t["type"] for t in ev["traps"]])


class CaseInsensitivity(unittest.TestCase):
    def test_lowercase_token_binds(self):
        ev = R.evaluate("user-agent: gptbot\ndisallow: /\n", ["GPTBot"])
        self.assertFalse(ev["bots"]["GPTBot"]["allowed"])

    def test_case_variant_trap(self):
        ev = R.evaluate("User-agent: GPTBOT\nDisallow: /\n", ["GPTBot"])
        self.assertIn("CASE_VARIANT_TOKEN", [t["type"] for t in ev["traps"]])


class Specificity(unittest.TestCase):
    TXT = ("User-agent: *\nDisallow: /\n\n"
           "User-agent: GPTBot\nAllow: /\n")

    def test_specific_group_disables_wildcard(self):
        ev = R.evaluate(self.TXT, ["GPTBot", "ClaudeBot"])
        self.assertTrue(ev["bots"]["GPTBot"]["allowed"])
        self.assertFalse(ev["bots"]["ClaudeBot"]["allowed"])

    def test_wildcard_blanket_trap_only_for_inheriting_bots(self):
        ev = R.evaluate(self.TXT, ["GPTBot", "ClaudeBot"])
        details = " ".join(t["detail"] for t in ev["traps"] if t["type"] == "WILDCARD_BLANKET_BLOCK")
        self.assertIn("ClaudeBot", details)
        self.assertNotIn("GPTBot", details)


class PathMatching(unittest.TestCase):
    TXT = "User-agent: GPTBot\nDisallow: /private\nAllow: /private/blog\n"

    def test_longest_match_wins(self):
        self.assertTrue(R.evaluate(self.TXT, ["GPTBot"], "/private/blog/post")["bots"]["GPTBot"]["allowed"])
        self.assertFalse(R.evaluate(self.TXT, ["GPTBot"], "/private/x")["bots"]["GPTBot"]["allowed"])

    def test_root_still_allowed_with_exclusions(self):
        ev = R.evaluate(self.TXT, ["GPTBot"])
        self.assertEqual(ev["bots"]["GPTBot"]["status"], "ALLOWED_WITH_EXCLUSIONS")

    def test_wildcard_and_anchor(self):
        txt = "User-agent: GPTBot\nDisallow: /*?session=\nDisallow: /tmp$\n"
        ev = R.evaluate(txt, ["GPTBot"], "/x?session=1")
        self.assertFalse(ev["bots"]["GPTBot"]["allowed"])
        self.assertFalse(R.evaluate(txt, ["GPTBot"], "/tmp")["bots"]["GPTBot"]["allowed"])
        self.assertTrue(R.evaluate(txt, ["GPTBot"], "/tmpfile")["bots"]["GPTBot"]["allowed"])

    def test_allow_wins_equal_length_tie(self):
        txt = "User-agent: GPTBot\nDisallow: /a\nAllow: /a\n"
        self.assertTrue(R.evaluate(txt, ["GPTBot"], "/a")["bots"]["GPTBot"]["allowed"])


class Edges(unittest.TestCase):
    def test_empty_disallow_allows(self):
        ev = R.evaluate("User-agent: *\nDisallow:\n", ["GPTBot"])
        self.assertTrue(ev["bots"]["GPTBot"]["allowed"])

    def test_no_robots_at_all(self):
        ev = R.evaluate("", ["GPTBot"])
        self.assertEqual(ev["bots"]["GPTBot"]["rule_source"], "no-group")
        self.assertTrue(ev["bots"]["GPTBot"]["allowed"])

    def test_comments_and_sitemaps(self):
        ev = R.evaluate("# hi\nSitemap: https://e.co/s.xml\nUser-agent: * # all\nDisallow: /x\n", ["GPTBot"])
        self.assertEqual(ev["sitemaps"], ["https://e.co/s.xml"])
        self.assertTrue(ev["bots"]["GPTBot"]["allowed"])

    def test_rules_before_any_user_agent_are_ignored(self):
        ev = R.evaluate("Disallow: /\nUser-agent: GPTBot\nAllow: /\n", ["GPTBot"])
        self.assertTrue(ev["bots"]["GPTBot"]["allowed"])

    def test_duplicate_groups_merge(self):
        txt = "User-agent: GPTBot\nDisallow: /a\n\nUser-agent: GPTBot\nDisallow: /b\n"
        self.assertFalse(R.evaluate(txt, ["GPTBot"], "/b")["bots"]["GPTBot"]["allowed"])


if __name__ == "__main__":
    unittest.main()
