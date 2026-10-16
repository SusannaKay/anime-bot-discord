import discord
from discord import app_commands
from typing import Callable


def _has_mod_permissions(member: discord.Member) -> bool:
    """
    Decides whether a member counts as a moderator.
    Criteria: common management permissions, or a role with "mod" in its name.
    """
    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages or perms.moderate_members:
        return True
    return any("mod" in role.name.lower() for role in member.roles)


def mod_only(check_name: str = "moderator"):
    """Builds a reusable check for admin/mod commands."""

    async def predicate(interaction: discord.Interaction) -> bool:
        user = interaction.user
        if isinstance(user, discord.Member) and _has_mod_permissions(user):
            return True
        raise app_commands.MissingPermissions([check_name])

    return app_commands.check(predicate)
