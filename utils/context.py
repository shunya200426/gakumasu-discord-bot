# utils/context.py

import logging
import sqlite3
from typing import Optional

import discord


log = logging.getLogger("gakumasu_bot")

_guild_repository = None


def configure_context_repository(guild_repository) -> None:
    """
    ログコンテキスト生成で使用するGuildRepositoryを設定する。

    Bot起動時にmain.pyから一度だけ呼び出す。
    """
    global _guild_repository
    _guild_repository = guild_repository
    log.info("GuildRepository configured for interaction context")


async def build_ctx_from_interaction(
    interaction: discord.Interaction,
) -> dict:
    """
    INFO/ERRORログに自動付与する文脈を構築する。
    """
    guild = getattr(interaction, "guild", None)
    user = getattr(interaction, "user", None)

    guild_id = getattr(guild, "id", None)
    guild_name = getattr(guild, "name", None) or "(DM)"

    community_name = "(unregistered)"

    if guild_id is not None and _guild_repository is not None:
        try:
            guild_data: Optional[sqlite3.Row] = (
                _guild_repository.get_by_guild_id(guild_id)
            )

            if guild_data is not None:
                community_name = (
                    guild_data["community_name"]
                    or "(unregistered)"
                )

        except Exception:
            log.warning(
                "Failed to get community name from database: guild_id=%s",
                guild_id,
                exc_info=True,
            )

    user_id = getattr(user, "id", None)
    user_name = (
        getattr(user, "display_name", None)
        or getattr(user, "global_name", None)
        or getattr(user, "name", None)
        or "(unknown)"
    )

    return {
        "guild_name": guild_name,
        "guild_id": str(guild_id) if guild_id is not None else "-",
        "circle_name": community_name,
        "user": user,
        "user_name": user_name,
        "user_id": str(user_id) if user_id is not None else "-",
    }