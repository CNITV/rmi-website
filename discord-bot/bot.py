"""RMI 2026 Discord bot.

- /setup    creează rolurile, categoriile și canalele (după profiles.py)
- /approve  dă un rol unui membru nou + îi setează nickname-ul după naming convention
- /revoke   scoate rolurile -> persoana nu mai vede nimic
- /pending  membrii care încă nu au niciun rol
Membrii noi nu văd nimic până îi aprobă un admin (vezi setup_server.py).
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from naming import NamingError, build_nick
from profiles import BOT_LOG, JOIN_REQUESTS, PROFILES, Profile
from teams import load_catalog, norm
from setup_server import apply_profile

load_dotenv()
log = logging.getLogger("rmi-bot")

intents = discord.Intents.default()
intents.members = True  # privilegiat: activează-l în Developer Portal -> Bot -> Server Members Intent


class RmiBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self) -> None:
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)  # comenzile apar imediat în fiecare server
        log.info("Conectat ca %s în %d servere", self.user, len(self.guilds))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        channel = discord.utils.get(member.guild.text_channels, name=JOIN_REQUESTS)
        if channel is None:
            return
        await channel.send(
            f"🆕 {member.mention} (`{member}`) a intrat și **nu vede nimic** până nu e aprobat.\n"
            f"Aprobă cu `/approve member:{member.name} role:...`",
            allowed_mentions=discord.AllowedMentions.none(),
        )


bot = RmiBot()
tree = bot.tree


# --- helpers -----------------------------------------------------------------


def profile_for(guild: discord.Guild) -> Profile | None:
    """Alege profilul: din ID-uri în .env, altfel după numele serverului (online / on-site)."""
    for key, profile in PROFILES.items():
        if os.getenv(f"RMI_{key.upper()}_GUILD_ID") == str(guild.id):
            return profile
    name = guild.name.lower().replace("-", "").replace(" ", "")
    if "onsite" in name:
        return PROFILES["onsite"]
    if "online" in name:
        return PROFILES["online"]
    return None


def _is_admin(interaction: discord.Interaction) -> bool:
    return isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator


async def _log(guild: discord.Guild, text: str) -> None:
    channel = discord.utils.get(guild.text_channels, name=BOT_LOG)
    if channel:
        await channel.send(text, allowed_mentions=discord.AllowedMentions.none())


def _profile_roles(guild: discord.Guild, profile: Profile) -> dict[str, discord.Role]:
    out = {}
    for spec in profile.roles:
        role = discord.utils.get(guild.roles, name=spec.name)
        if role:
            out[spec.key] = role
    return out


async def _role_autocomplete(interaction: discord.Interaction, current: str):
    profile = profile_for(interaction.guild) if interaction.guild else None
    if profile is None:
        return []
    return [
        app_commands.Choice(name=r.name, value=r.key)
        for r in profile.roles
        if current.lower() in r.name.lower() or current.lower() in r.key
    ]



def _matches(current: str, *haystacks: str) -> bool:
    q = norm(current)
    return not q or any(q in norm(h) for h in haystacks)


async def _country_autocomplete(interaction: discord.Interaction, current: str):
    profile = profile_for(interaction.guild) if interaction.guild else None
    if profile is None:
        return []
    return [
        app_commands.Choice(name=c.label, value=c.name)
        for c in load_catalog().for_profile(profile.key)
        if _matches(current, c.name, c.iso)
    ][:25]


async def _team_autocomplete(interaction: discord.Interaction, current: str):
    profile = profile_for(interaction.guild) if interaction.guild else None
    chosen = getattr(interaction.namespace, "country", None)
    if profile is None or not chosen:
        return []  # întâi țara
    country = load_catalog().find_country(chosen, profile.key)
    if country is None:
        return []
    return [
        app_commands.Choice(name=f"{t.name} ({t.code})"[:100], value=t.name[:100])
        for t in country.teams
        if _matches(current, t.name, t.code)
    ][:25]


# --- comenzi -----------------------------------------------------------------


@tree.command(name="setup", description="Creează rolurile, categoriile și canalele RMI pe acest server.")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
@app_commands.describe(profil="Doar dacă numele serverului nu conține „online” / „on-site”")
@app_commands.choices(profil=[app_commands.Choice(name=p.label, value=p.key) for p in PROFILES.values()])
async def setup_cmd(interaction: discord.Interaction, profil: str | None = None):
    if not _is_admin(interaction):
        return await interaction.response.send_message("Doar adminii pot rula /setup.", ephemeral=True)
    guild = interaction.guild
    profile = PROFILES[profil] if profil else profile_for(guild)
    if profile is None:
        return await interaction.response.send_message(
            "Nu știu ce profil să aplic. Rulează `/setup profil:...`.", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        report = await apply_profile(guild, profile)
    except discord.Forbidden:
        return await interaction.followup.send(
            "❌ Nu am permisiunea. Pune rolul botului **deasupra** celorlalte roluri "
            "(Server Settings → Roles) și invită-l cu permisiunea Administrator.",
            ephemeral=True,
        )
    await interaction.followup.send(
        f"✅ **{profile.label}** configurat ({len(report)} pași).\n"
        "Acum dă-ți ție (și celorlalți admini) rolul **Admin**, apoi folosește `/approve`.",
        ephemeral=True,
    )
    await _log(guild, f"⚙️ {interaction.user.mention} a rulat /setup ({profile.label}).")


@tree.command(name="approve", description="Aprobă un membru: îi dă rolul și nickname-ul corect.")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
@app_commands.autocomplete(role=_role_autocomplete, country=_country_autocomplete, team=_team_autocomplete)
@app_commands.describe(
    member="Persoana de aprobat",
    role="Rolul",
    country="Țara (lista cu steaguri; doar țările înscrise). Pentru Team Leader / Contestant",
    team="Echipa (apare după ce alegi țara). Doar la on-site, pentru Team Leader / Contestant",
    name="Numele de afișat (implicit: numele de pe Discord)",
)
async def approve(
    interaction: discord.Interaction,
    member: discord.Member,
    role: str,
    country: str | None = None,
    team: str | None = None,
    name: str | None = None,
):
    if not _is_admin(interaction):
        return await interaction.response.send_message("Doar adminii pot aproba.", ephemeral=True)
    guild = interaction.guild
    profile = profile_for(guild)
    if profile is None:
        return await interaction.response.send_message("Rulează mai întâi `/setup`.", ephemeral=True)
    try:
        spec = profile.role(role)
    except KeyError:
        return await interaction.response.send_message("Rol necunoscut — alege din listă.", ephemeral=True)
    roles = _profile_roles(guild, profile)
    if spec.key not in roles:
        return await interaction.response.send_message("Rolul nu există încă. Rulează `/setup`.", ephemeral=True)
    iso = team_code = None
    place = ""
    if "country" in spec.required_fields:
        catalog = load_catalog()
        if not catalog.countries:
            return await interaction.response.send_message("❌ Lipsește lista de echipe (data/participants_2026.csv).", ephemeral=True)
        if not country:
            return await interaction.response.send_message("❌ Alege țara din listă.", ephemeral=True)
        found = catalog.find_country(country, profile.key)
        if found is None:
            return await interaction.response.send_message(
                f"❌ „{country}” nu e o țară înscrisă. Alege din listă.", ephemeral=True
            )
        iso, place = found.iso, found.label
        if "team" in spec.required_fields:
            if not team:
                return await interaction.response.send_message("❌ Alege echipa din listă.", ephemeral=True)
            found_team = catalog.find_team(found, team)
            if found_team is None:
                return await interaction.response.send_message(
                    f"❌ „{team}” nu e o echipă din {found.name} (on-site). Alege din listă.", ephemeral=True
                )
            team_code, place = found_team.code, f"{found.label} · {found_team.name}"
    try:
        nick = build_nick(spec, name or member.display_name, iso, team_code)
    except NamingError as e:
        return await interaction.response.send_message(f"❌ {e}", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    others = [r for k, r in roles.items() if k != spec.key and r in member.roles]
    try:
        if others:
            await member.remove_roles(*others, reason=f"RMI bot: /approve de {interaction.user}")
        await member.add_roles(roles[spec.key], reason=f"RMI bot: /approve de {interaction.user}")
    except discord.Forbidden:
        return await interaction.followup.send(
            "❌ Nu pot schimba rolurile acestei persoane (rolul botului trebuie să fie mai sus).", ephemeral=True
        )
    nick_note = ""
    try:
        await member.edit(nick=nick, reason="RMI bot: naming convention")
    except discord.Forbidden:
        nick_note = f"\n⚠️ Rol acordat, dar nu am putut schimba nickname-ul (owner/rol mai sus). Setează-l manual: `{nick}`"
    await interaction.followup.send(f"✅ {member.mention} → **{spec.name}**{f' · {place}' if place else ''} · `{nick}`{nick_note}", ephemeral=True)
    await _log(guild, f"✅ {interaction.user.mention} a aprobat {member.mention} ca **{spec.name}**{f' ({place})' if place else ''} · `{nick}`.")


@tree.command(name="revoke", description="Scoate rolurile RMI unui membru (nu mai vede nimic).")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def revoke(interaction: discord.Interaction, member: discord.Member):
    if not _is_admin(interaction):
        return await interaction.response.send_message("Doar adminii pot revoca.", ephemeral=True)
    guild = interaction.guild
    profile = profile_for(guild)
    if profile is None:
        return await interaction.response.send_message("Rulează mai întâi `/setup`.", ephemeral=True)
    held = [r for r in _profile_roles(guild, profile).values() if r in member.roles]
    await interaction.response.defer(ephemeral=True)
    try:
        if held:
            await member.remove_roles(*held, reason=f"RMI bot: /revoke de {interaction.user}")
        await member.edit(nick=None, reason="RMI bot: /revoke")
    except discord.Forbidden:
        return await interaction.followup.send("❌ Nu am permisiunea pe această persoană.", ephemeral=True)
    await interaction.followup.send(f"🚫 {member.mention} nu mai are acces.", ephemeral=True)
    await _log(guild, f"🚫 {interaction.user.mention} a revocat accesul lui {member.mention}.")


@tree.command(name="pending", description="Membrii care așteaptă aprobare (fără niciun rol RMI).")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def pending(interaction: discord.Interaction):
    if not _is_admin(interaction):
        return await interaction.response.send_message("Doar adminii.", ephemeral=True)
    guild = interaction.guild
    profile = profile_for(guild)
    if profile is None:
        return await interaction.response.send_message("Rulează mai întâi `/setup`.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    rmi_ids = {r.id for r in _profile_roles(guild, profile).values()}
    waiting = [
        m async for m in guild.fetch_members(limit=None)
        if not m.bot and not any(r.id in rmi_ids for r in m.roles)
    ]
    if not waiting:
        return await interaction.followup.send("Nimeni nu așteaptă aprobare. 🎉", ephemeral=True)
    lines = [f"• {m.mention} (`{m}`)" for m in waiting[:40]]
    more = f"\n… și încă {len(waiting) - 40}" if len(waiting) > 40 else ""
    await interaction.followup.send(f"**{len(waiting)} în așteptare:**\n" + "\n".join(lines) + more, ephemeral=True)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Lipsește DISCORD_TOKEN (vezi .env.example).")
    logging.basicConfig(level=logging.INFO)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
