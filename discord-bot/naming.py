"""Naming convention: `[ISC] Livia Magureanu`, `[RO-TL] Livia Magureanu`, `[RO-A1] Nume`."""
from __future__ import annotations

import re

from profiles import RoleSpec

NICK_MAX = 32  # limita Discord

_COUNTRY = re.compile(r"[A-Za-z]{2,3}")
_TEAM = re.compile(r"[A-Za-z0-9]{1,6}")


class NamingError(ValueError):
    pass


def build_nick(role: RoleSpec, name: str, country: str | None = None, team: str | None = None) -> str:
    fields: dict[str, str] = {}
    for field in role.required_fields:
        value = {"country": country, "team": team}[field]
        if not value:
            raise NamingError(f"Rolul „{role.name}” cere parametrul `{field}`.")
        pattern = _COUNTRY if field == "country" else _TEAM
        if not pattern.fullmatch(value):
            hint = "2-3 litere, ex. RO" if field == "country" else "1-6 litere/cifre, ex. V3"
            raise NamingError(f"`{field}` invalid: „{value}” ({hint}).")
        fields[field] = value.upper()

    name = " ".join(name.split())
    if not name:
        raise NamingError("Numele este gol.")
    prefix = f"[{role.tag.format(**fields)}] "
    room = NICK_MAX - len(prefix)
    if room < 3:
        raise NamingError("Prefixul e prea lung pentru un nickname Discord.")
    return prefix + name[:room].rstrip()
