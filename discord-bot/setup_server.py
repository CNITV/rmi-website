"""Creează/actualizează rolurile, categoriile și canalele unui server după un Profile.

Idempotent: poți rula de câte ori vrei. Nu șterge nimic. Permisiunile categoriilor și
canalelor din profil sunt readuse la starea din `profiles.py` la fiecare rulare.
"""
from __future__ import annotations

import discord

from profiles import CategorySpec, ChannelSpec, Profile, RoleSpec

REASON = "RMI bot: /setup"

# Ce poate face orice rol aprobat. `view_channel` lipsește intenționat: vizibilitatea
# se acordă doar prin categorii, deci un membru fără rol (sau un canal nou, în afara
# categoriilor) nu vede nimic.
_MEMBER = dict(
    send_messages=True,
    send_messages_in_threads=True,
    read_message_history=True,
    add_reactions=True,
    attach_files=True,
    embed_links=True,
    use_external_emojis=True,
    use_application_commands=True,
    connect=True,
    speak=True,
    use_voice_activation=True,
    # change_nickname=False: nickname-ul este gestionat de bot (naming convention)
)


def role_permissions(spec: RoleSpec) -> discord.Permissions:
    if spec.level == "admin":
        return discord.Permissions(administrator=True)
    perms = discord.Permissions(**_MEMBER)
    if spec.level == "elevated":
        perms.update(manage_channels=True)  # voluntari/organizatori pot crea canale noi
    return perms


async def ensure_roles(guild: discord.Guild, profile: Profile, report: list[str]) -> dict[str, discord.Role]:
    roles: dict[str, discord.Role] = {}
    for spec in profile.roles:
        perms = role_permissions(spec)
        role = discord.utils.get(guild.roles, name=spec.name)
        kwargs = dict(
            colour=discord.Colour(spec.color),
            hoist=spec.hoist,
            mentionable=False,
            permissions=perms,
            reason=REASON,
        )
        if role is None:
            role = await guild.create_role(name=spec.name, **kwargs)
            report.append(f"rol creat: {spec.name}")
        else:
            await role.edit(**kwargs)
            report.append(f"rol actualizat: {spec.name}")
        roles[spec.key] = role
    return roles


def _category_overwrites(
    guild: discord.Guild, roles: dict[str, discord.Role], spec: CategorySpec
) -> dict[discord.Role, discord.PermissionOverwrite]:
    ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for key in spec.visible_to:
        ow[roles[key]] = discord.PermissionOverwrite(view_channel=True)
    return ow


def _channel_overwrites(
    base: dict[discord.Role, discord.PermissionOverwrite],
    roles: dict[str, discord.Role],
    spec: ChannelSpec,
    visible_to: tuple[str, ...],
) -> dict[discord.Role, discord.PermissionOverwrite]:
    ow = dict(base)
    if spec.writers is not None and spec.kind == "text":
        for key in visible_to:
            ow[roles[key]] = discord.PermissionOverwrite(
                view_channel=True, send_messages=key in spec.writers
            )
    return ow


async def _ensure_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    spec: ChannelSpec,
    overwrites: dict,
    report: list[str],
) -> None:
    pool = category.voice_channels if spec.kind == "voice" else category.text_channels
    channel = discord.utils.get(pool, name=spec.name if spec.kind == "voice" else spec.name.lower())
    if channel is None:
        if spec.kind == "voice":
            await guild.create_voice_channel(spec.name, category=category, overwrites=overwrites, reason=REASON)
        else:
            await guild.create_text_channel(
                spec.name, category=category, overwrites=overwrites, topic=spec.topic or None, reason=REASON
            )
        report.append(f"canal creat: {spec.name}")
    else:
        if spec.kind == "text":
            await channel.edit(overwrites=overwrites, topic=spec.topic or None, reason=REASON)
        else:
            await channel.edit(overwrites=overwrites, reason=REASON)
        report.append(f"canal actualizat: {spec.name}")


async def apply_profile(guild: discord.Guild, profile: Profile) -> list[str]:
    """Aduce serverul la starea din profil. Returnează o listă de rânduri pentru raport."""
    report: list[str] = []

    # @everyone nu poate face nimic -> un membru nou nu vede niciun canal până primește un rol.
    await guild.default_role.edit(permissions=discord.Permissions.none(), reason=REASON)
    report.append("@everyone: toate permisiunile scoase (membrii noi nu văd nimic)")

    roles = await ensure_roles(guild, profile, report)

    for cat_spec in profile.categories:
        cat_ow = _category_overwrites(guild, roles, cat_spec)
        category = discord.utils.get(guild.categories, name=cat_spec.name)
        if category is None:
            category = await guild.create_category(cat_spec.name, overwrites=cat_ow, reason=REASON)
            report.append(f"categorie creată: {cat_spec.name}")
        else:
            await category.edit(overwrites=cat_ow, reason=REASON)
            report.append(f"categorie actualizată: {cat_spec.name}")
        for ch_spec in cat_spec.channels:
            ow = _channel_overwrites(cat_ow, roles, ch_spec, cat_spec.visible_to)
            await _ensure_channel(guild, category, ch_spec, ow, report)
    return report
