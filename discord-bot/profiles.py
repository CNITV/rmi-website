"""Definițiile celor două servere RMI 2026: roluri, naming convention, categorii, canale.

Tot ce ține de "cum arată serverul" e aici. Modifici lista, rulezi din nou `/setup`
și botul aduce serverul la starea descrisă (nu șterge niciodată nimic).
"""
from __future__ import annotations

from dataclasses import dataclass
from string import Formatter

# --- Roluri -----------------------------------------------------------------


@dataclass(frozen=True)
class RoleSpec:
    key: str  # id intern, folosit în comenzi și în vizibilitatea categoriilor
    name: str  # numele rolului pe Discord
    color: int
    tag: str  # șablonul din [] din nickname; {country} și {team} sunt completate la /approve
    level: str = "member"  # admin | elevated | member
    hoist: bool = True  # afișat separat în lista de membri

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f for _, f, _, _ in Formatter().parse(self.tag) if f)


# --- Canale -----------------------------------------------------------------


@dataclass(frozen=True)
class ChannelSpec:
    name: str
    kind: str = "text"  # text | voice
    topic: str = ""
    # None = oricine vede canalul poate scrie. Altfel: doar rolurile din listă (+ Admin) pot scrie.
    writers: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CategorySpec:
    name: str
    visible_to: tuple[str, ...]  # cheile rolurilor care văd categoria (Admin vede tot oricum)
    channels: tuple[ChannelSpec, ...]


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    roles: tuple[RoleSpec, ...]
    categories: tuple[CategorySpec, ...]

    def role(self, key: str) -> RoleSpec:
        for r in self.roles:
            if r.key == key:
                return r
        raise KeyError(key)


# Canale folosite de bot (create de /setup)
JOIN_REQUESTS = "join-requests"
BOT_LOG = "bot-log"

ADMIN_CATEGORY = CategorySpec(
    name="🛠 ADMIN",
    visible_to=(),
    channels=(
        ChannelSpec(JOIN_REQUESTS, topic="Cine a intrat și așteaptă aprobare. Folosește /approve."),
        ChannelSpec(BOT_LOG, topic="Jurnal: cine a aprobat/revocat pe cine."),
    ),
)

# --- Server ONLINE (traduceri) -----------------------------------------------

ONLINE = Profile(
    key="online",
    label="RMI 2026 Online (traduceri)",
    roles=(
        RoleSpec("admin", "Admin", 0xE74C3C, "ADMIN", level="admin"),
        RoleSpec("isc", "Scientific Committee", 0x9B59B6, "ISC"),
        RoleSpec("tl", "Team Leader", 0x3498DB, "{country}-TL"),
    ),
    categories=(
        CategorySpec(
            "📢 INFO",
            ("isc", "tl"),
            (
                ChannelSpec("announcements", topic="Anunțuri oficiale.", writers=("isc",)),
                ChannelSpec("general"),
                ChannelSpec("q-and-a", topic="Întrebări despre procesul de traducere."),
            ),
        ),
        CategorySpec(
            "🌐 TRANSLATIONS",
            ("isc", "tl"),
            (
                ChannelSpec("translations", topic="Discuții despre traduceri."),
                ChannelSpec("translation-questions", topic="Întrebări despre enunțuri."),
            ),
        ),
        CategorySpec(
            "🧑‍✈️ TEAM LEADERS",
            ("isc", "tl"),
            (ChannelSpec("team-leaders"),),
        ),
        CategorySpec(
            "🔒 ISC",
            ("isc",),
            (
                ChannelSpec("isc-private"),
                ChannelSpec("ISC room", kind="voice"),
            ),
        ),
        CategorySpec(
            "🎙 MEETING ROOMS",
            ("isc", "tl"),
            tuple(ChannelSpec(f"Meeting room {i}", kind="voice") for i in range(1, 5)),
        ),
        ADMIN_CATEGORY,
    ),
)

# --- Server ON-SITE ----------------------------------------------------------

ONSITE = Profile(
    key="onsite",
    label="RMI 2026 On-site",
    roles=(
        RoleSpec("admin", "Admin", 0xE74C3C, "ADMIN", level="admin"),
        RoleSpec("org", "Organizing Committee", 0xE67E22, "ORG", level="elevated"),
        RoleSpec("vol", "Volunteer", 0x2ECC71, "VOL", level="elevated"),
        RoleSpec("tl", "Team Leader", 0x3498DB, "{country}-{team} TL"),
        RoleSpec("contestant", "Contestant", 0xF1C40F, "{country}-{team}", hoist=False),
    ),
    categories=(
        CategorySpec(
            "📢 INFO",
            ("org", "vol", "tl", "contestant"),
            (
                ChannelSpec("announcements", topic="Anunțuri oficiale.", writers=("org",)),
                ChannelSpec("general"),
                ChannelSpec("q-and-a", topic="Orice întrebare despre eveniment."),
                ChannelSpec("arrivals", topic="Anunțați-vă sosirea: oră, zbor/tren, locație."),
            ),
        ),
        CategorySpec(
            "🙋 VOLUNTEERS",
            ("org", "vol"),
            (
                ChannelSpec("volunteers"),
                ChannelSpec("volunteer-issues", topic="Probleme apărute pe teren."),
            ),
        ),
        CategorySpec("🎯 ORGANIZERS", ("org",), (ChannelSpec("organizers"),)),
        CategorySpec("🧑‍✈️ TEAM LEADERS", ("org", "tl"), (ChannelSpec("team-leaders"),)),
        ADMIN_CATEGORY,
    ),
)

PROFILES: dict[str, Profile] = {p.key: p for p in (ONLINE, ONSITE)}
