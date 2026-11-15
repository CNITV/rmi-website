import asyncio
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import teams  # noqa: E402
from naming import build_nick  # noqa: E402
from profiles import PROFILES  # noqa: E402


class Catalog(unittest.TestCase):
    def setUp(self):
        self.cat = teams.load_catalog()

    def test_every_country_in_csv_has_iso(self):
        import csv

        with teams.DEFAULT_CSV.open(encoding="utf-8") as fh:
            names = {r["country"] for r in csv.DictReader(fh)}
        self.assertEqual(names, {c.name for c in self.cat.countries})

    def test_flags(self):
        ro = self.cat.find_country("romania", "online")
        self.assertEqual(ro.flag, "🇷🇴")
        self.assertEqual(self.cat.find_country("Turkiye", "online").iso, "TR")  # fără diacritice
        self.assertEqual(self.cat.find_country("🇷🇴 Romania", "online").name, "Romania")

    def test_codes_unique_and_short_within_country(self):
        for c in self.cat.countries:
            codes = [t.code for t in c.teams]
            self.assertEqual(len(codes), len(set(codes)), c.name)
            for code in codes:
                self.assertTrue(1 <= len(code) <= teams.MAX_CODE and code.isalnum(), (c.name, code))

    def test_code_examples(self):
        ro = self.cat.find_country("Romania", "online")
        by = {t.name: t.code for t in ro.teams}
        self.assertEqual(by["Romania 1"], "1")
        self.assertEqual(by["Vianu 3"], "V3")
        self.assertEqual(by["Romania Juniors 1"], "J1")
        self.assertEqual(self.cat.find_team(ro, "Vianu 3 (V3)").name, "Vianu 3")

    def test_onsite_only_lists_onsite(self):
        online = {c.name for c in self.cat.for_profile("online")}
        onsite = {c.name for c in self.cat.for_profile("onsite")}
        self.assertTrue(onsite < online)
        self.assertNotIn("Italy", onsite)  # doar online
        for c in self.cat.for_profile("onsite"):
            self.assertTrue(all(t.participation == "On-site" for t in c.teams))
        self.assertIsNone(self.cat.find_country("Italy", "onsite"))

    def test_nickname_from_catalog(self):
        c = self.cat.find_country("Romania", "onsite")
        t = self.cat.find_team(c, "Vianu 3")
        self.assertEqual(build_nick(PROFILES["onsite"].role("tl"), "Ana", c.iso, t.code), "[RO-V3 TL] Ana")
        self.assertEqual(build_nick(PROFILES["online"].role("tl"), "Ana", c.iso), "[RO-TL] Ana")


class Autocomplete(unittest.TestCase):
    def _inter(self, guild_name, country=None):
        return SimpleNamespace(guild=SimpleNamespace(name=guild_name, id=1), namespace=SimpleNamespace(country=country))

    def test_country_dropdown_has_flags_and_filters(self):
        import bot

        res = asyncio.run(bot._country_autocomplete(self._inter("RMI 2026 on-site"), ""))
        names = [c.name for c in res]
        self.assertIn("🇷🇴 Romania", names)
        self.assertNotIn("🇮🇹 Italy", names)  # on-site: doar țările cu echipe on-site
        online = asyncio.run(bot._country_autocomplete(self._inter("RMI 2026 online"), ""))
        self.assertIn("🇮🇹 Italy", [c.name for c in online])
        res = asyncio.run(bot._country_autocomplete(self._inter("RMI 2026 online"), "turk"))
        self.assertEqual([c.value for c in res], ["Türkiye"])

    def test_team_dropdown_depends_on_country(self):
        import bot

        self.assertEqual(asyncio.run(bot._team_autocomplete(self._inter("RMI 2026 on-site"), "")), [])
        res = asyncio.run(bot._team_autocomplete(self._inter("RMI 2026 on-site", "Romania"), "vianu"))
        self.assertTrue(res and all("Vianu" in c.value for c in res))
        res = asyncio.run(bot._team_autocomplete(self._inter("RMI 2026 on-site", "Bulgaria"), ""))
        self.assertTrue(all(len(c.name) <= 100 for c in res) and len(res) <= 25)


if __name__ == "__main__":
    unittest.main()
