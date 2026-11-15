import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from naming import NamingError, build_nick  # noqa: E402
from profiles import PROFILES  # noqa: E402


class Naming(unittest.TestCase):
    def test_isc_and_tl(self):
        on = PROFILES["online"]
        self.assertEqual(build_nick(on.role("isc"), "Livia Magureanu"), "[ISC] Livia Magureanu")
        self.assertEqual(build_nick(on.role("tl"), "Livia Magureanu", country="ro"), "[RO-TL] Livia Magureanu")

    def test_onsite_team_code(self):
        os_ = PROFILES["onsite"]
        self.assertEqual(build_nick(os_.role("contestant"), "Ana", "ro", "a1"), "[RO-A1] Ana")
        self.assertEqual(build_nick(os_.role("tl"), "Ana", "ro", "a1"), "[RO-A1 TL] Ana")
        self.assertEqual(build_nick(os_.role("vol"), "Ana"), "[VOL] Ana")

    def test_missing_or_invalid_fields(self):
        tl = PROFILES["online"].role("tl")
        with self.assertRaises(NamingError):
            build_nick(tl, "Ana")
        with self.assertRaises(NamingError):
            build_nick(tl, "Ana", country="Romania")
        with self.assertRaises(NamingError):
            build_nick(PROFILES["onsite"].role("contestant"), "Ana", "RO")

    def test_max_32_chars(self):
        nick = build_nick(PROFILES["onsite"].role("tl"), "A" * 80, "RO", "A1")
        self.assertLessEqual(len(nick), 32)
        self.assertTrue(nick.startswith("[RO-A1 TL] "))


class ProfileConsistency(unittest.TestCase):
    def test_references_resolve(self):
        for p in PROFILES.values():
            keys = {r.key for r in p.roles}
            self.assertIn("admin", keys)
            for c in p.categories:
                self.assertTrue(set(c.visible_to) <= keys, c.name)
                for ch in c.channels:
                    self.assertTrue(set(ch.writers or ()) <= set(c.visible_to), ch.name)

    def test_unique_names(self):
        for p in PROFILES.values():
            names = [ch.name for c in p.categories for ch in c.channels]
            self.assertEqual(len(names), len(set(names)))

    def test_bot_channels_are_admin_only(self):
        for p in PROFILES.values():
            admin_cat = next(c for c in p.categories if "ADMIN" in c.name)
            self.assertEqual(admin_cat.visible_to, ())


class Imports(unittest.TestCase):
    def test_bot_imports(self):
        import bot  # noqa: F401
        self.assertEqual({c.name for c in bot.tree.get_commands()}, {"setup", "approve", "revoke", "pending"})


if __name__ == "__main__":
    unittest.main()
