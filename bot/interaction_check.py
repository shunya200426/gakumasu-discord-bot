# Standard library
import asyncio
from collections.abc import Awaitable, Callable

# Third-party
import discord
from discord import Embed

# Local application
from bot.developer_notifier import notify_dev_about_block
from services.interaction_access_service import (
    AccessDeniedReason,
    InteractionAccessResult,
)
from utils.logger import get_logger

log = get_logger()


ACCESS_DENIED_COLOR_MAP = {
    AccessDeniedReason.USER_BLOCKED: 0xE74C3C,
    AccessDeniedReason.DM_NOT_ALLOWED: 0xFF9900,
    AccessDeniedReason.GUILD_NOT_REGISTERED: 0xE53935,
    AccessDeniedReason.GUILD_DISABLED: 0xE53935,
}


async def _send_internal_error_message(
    interaction: discord.Interaction,
) -> None:
    embed = Embed(
        color=0xE53935,
        description=(
            "### ⚠️ 内部エラーが発生しました\n"
            "しばらく時間を空けてから、"
            "もう一度お試しください。"
        ),
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

    except Exception:
        log.debug(
            "Failed to send internal error message",
            exc_info=True,
        )


async def _send_access_denied_message(
    interaction: discord.Interaction,
    result: InteractionAccessResult,
) -> None:
    denied_reason = result.denied_reason

    if denied_reason is None:
        await _send_internal_error_message(
            interaction
        )
        return

    color = ACCESS_DENIED_COLOR_MAP.get(
        denied_reason,
        0xE53935,
    )

    message = (
        result.user_message
        or "このコマンドは現在利用できません。"
    )

    embed = Embed(
        color=color,
        description=message,
    )

    try:
        await interaction.response.send_message(
            embed=embed,
            ephemeral=False,
        )

    except Exception:
        log.debug(
            "Failed to send access denied message",
            exc_info=True,
        )


def create_interaction_access_check(
    *,
    dev_user_id: int,
    alert_channel_id: int,
    cooldown_per_guild: int,
    cooldown_per_user: int,
    cooldown_global: int,
) -> Callable[
    [discord.Interaction],
    Awaitable[bool],
]:
    """
    グローバルなSlash Commandアクセスチェックを生成する。

    開発者通知に必要な設定値を外部から受け取り、
    main.pyへの依存を持たせない。
    """

    async def interaction_access_check(
        interaction: discord.Interaction,
    ) -> bool:
        service = getattr(
            interaction.client,
            "interaction_access_service",
            None,
        )

        if service is None:
            raise RuntimeError(
                "InteractionAccessServiceが"
                "初期化されていません。"
            )

        guild = interaction.guild
        user = interaction.user

        guild_id = getattr(
            guild,
            "id",
            None,
        )
        guild_name = getattr(
            guild,
            "name",
            "(DMまたは不明)",
        )
        user_id = getattr(
            user,
            "id",
            None,
        )

        command_name = getattr(
            getattr(
                interaction,
                "command",
                None,
            ),
            "qualified_name",
            None,
        )

        log.debug(
            "interaction_access_check called: "
            "guild=%s id=%s user=%s cmd=%s",
            guild_name,
            guild_id,
            user_id,
            command_name,
        )

        try:
            result = service.check_access(
                interaction
            )

        except Exception:
            log.exception(
                "Interaction access check failed: "
                "guild_id=%s user_id=%s cmd=%s",
                guild_id,
                user_id,
                command_name,
            )

            await _send_internal_error_message(
                interaction
            )

            return False

        if result.allowed:
            return True

        denied_reason = result.denied_reason

        if denied_reason is None:
            log.error(
                "Interaction access denied "
                "without denied_reason: "
                "guild_id=%s user_id=%s cmd=%s",
                guild_id,
                user_id,
                command_name,
            )

            await _send_internal_error_message(
                interaction
            )

            return False

        asyncio.create_task(
            notify_dev_about_block(
                bot=interaction.client,
                reason=denied_reason.value,
                interaction=interaction,
                dev_user_id=dev_user_id,
                alert_channel_id=alert_channel_id,
                cooldown_per_guild=cooldown_per_guild,
                cooldown_per_user=cooldown_per_user,
                cooldown_global=cooldown_global,
            )
        )

        await _send_access_denied_message(
            interaction=interaction,
            result=result,
        )

        log.warning(
            "Interaction access denied: "
            "guild_id=%s user_id=%s cmd=%s "
            "reason=%s internal_reason=%s",
            guild_id,
            user_id,
            command_name,
            denied_reason.value,
            result.internal_reason,
        )

        return False

    return interaction_access_check