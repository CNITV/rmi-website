"""Țările și echipele înscrise, citite din data/participants_2026.csv (aceeași sursă ca pagina de participanți).

Fișierul se re-citește când se schimbă, deci după un `git pull` dropdown-urile se actualizează fără restart.
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "participants_2026.csv"

# Nume de țară (cum apare în CSV) -> cod ISO 3166-1 alpha-2 (folosit în nickname și pentru steag).
COUNTRY_CODES = {
    "Azerbaijan": "AZ",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Cyprus": "CY",
    "Georgia": "GE",
    "Greece": "GR",
    "Hungary": "HU",
    "Italy": "IT",
    "Moldova": "MD",
    "Romania": "RO",
    "Serbia": "RS",
    "Türkiye": "TR",
    "Ukraine": "UA",
    "Vietnam": "VN",
}

# Coduri de echipă setate manual: (țară, nume echipă) -> cod (max 6 caractere, litere/cifre).
TEAM_CODE_OVERRIDES: dict[tuple[str, str], str] = {}

MAX_CODE = 6


def _ascii(text: str) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def norm(text: str) -> str:
    """Pentru căutare: fără diacritice, litere mici, fără steag/spații în plus."""
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", _ascii(text).lower()).split())


def flag_emoji(iso: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


@dataclass(frozen=True)
class Team:
    name: str
    code: str
    participation: str  # "On-site" | "Online"


@dataclass(frozen=True)
class Country:
    name: str
    iso: str
    teams: tuple[Team, ...]

    @property
    def flag(self) -> str:
        return flag_emoji(self.iso)

    @property
    def label(self) -> str:
        return f"{self.flag} {self.name}"


def _base_code(team_name: str, country_name: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", _ascii(team_name))
    country_tokens = re.findall(r"[A-Za-z0-9]+", _ascii(country_name).lower())
    # „Georgia Team 1” -> „Team 1”: țara e deja în prefix
    if tokens[: len(country_tokens)] and [t.lower() for t in tokens[: len(country_tokens)]] == country_tokens:
        tokens = tokens[len(country_tokens):]
    def part(t: str) -> str:  # ALGO1 -> A1, Team -> T, 03 -> 03
        if t.isdigit():
            return t
        m = re.search(r"\d+$", t)
        return t[0].upper() + (m.group() if m else "")

    code = "".join(part(t) for t in tokens)
    return (code or "1")[:MAX_CODE].upper()


def _assign_codes(country: str, names: list[str]) -> dict[str, str]:
    codes: dict[str, str] = {}
    used: set[str] = set()
    for name in sorted(names):
        code = TEAM_CODE_OVERRIDES.get((country, name)) or _base_code(name, country)
        candidate, n = code, 1
        while candidate in used:  # coliziune în aceeași țară: V1, V1B, V1C...
            n += 1
            suffix = chr(ord("A") + n - 1) if n <= 26 else str(n)
            candidate = code[: MAX_CODE - len(suffix)] + suffix
        used.add(candidate)
        codes[name] = candidate
    return codes


class Catalog:
    def __init__(self, countries: list[Country]):
        self.countries = sorted(countries, key=lambda c: c.name)

    def for_profile(self, profile_key: str) -> list[Country]:
        """Online: toate țările. On-site: doar țările cu echipe On-site (și doar acele echipe)."""
        if profile_key != "onsite":
            return self.countries
        out = []
        for c in self.countries:
            teams = tuple(t for t in c.teams if t.participation == "On-site")
            if teams:
                out.append(Country(c.name, c.iso, teams))
        return out

    def find_country(self, text: str, profile_key: str) -> Country | None:
        wanted = norm(text)
        for c in self.for_profile(profile_key):
            if wanted in (norm(c.name), c.iso.lower(), norm(c.label)):
                return c
        return None

    def find_team(self, country: Country, text: str) -> Team | None:
        wanted = norm(text)
        for t in country.teams:
            if wanted in (norm(t.name), norm(f"{t.name} {t.code}"), norm(f"{t.name} ({t.code})")):
                return t
        return None


_cache: tuple[Path, float, Catalog] | None = None


def load_catalog(path: str | os.PathLike | None = None) -> Catalog:
    global _cache
    p = Path(path or os.getenv("RMI_TEAMS_CSV") or DEFAULT_CSV)
    if not p.exists():
        return Catalog([])
    mtime = p.stat().st_mtime
    if _cache and _cache[0] == p and _cache[1] == mtime:
        return _cache[2]
    by_country: dict[str, list[dict]] = {}
    with p.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("country") and row.get("team"):
                by_country.setdefault(row["country"].strip(), []).append(row)
    countries = []
    for name, rows in by_country.items():
        iso = COUNTRY_CODES.get(name)
        if iso is None:
            continue  # țară necunoscută: adaug-o în COUNTRY_CODES (testele o prind)
        codes = _assign_codes(name, [r["team"].strip() for r in rows])
        teams = tuple(
            sorted(
                (Team(r["team"].strip(), codes[r["team"].strip()], r.get("participation", "").strip()) for r in rows),
                key=lambda t: t.name,
            )
        )
        countries.append(Country(name, iso, teams))
    catalog = Catalog(countries)
    _cache = (p, mtime, catalog)
    return catalog
