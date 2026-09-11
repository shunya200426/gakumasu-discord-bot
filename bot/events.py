# Standard library
import traceback

# Third-party
import discord
from discord.ext import commands

# Local application
from utils.context import build_ctx_from_interaction
from utils.logger import (
    get_logger,
    use_log_context,
)

log = get_logger()


def register_events(
    bot: commands.Bot,
    *,
    sync_mode: str,
    test_guild_id: str | None,
) -> None:
    """
    Discordイベントと管理用Prefix CommandをBotへ登録する。
    """

    @bot.event
    async def on_ready() -> None:
        log.info(
            "✅ Logged in as %s (%s)",
            bot.user,
            (
                bot.user.id
                if bot.user
                else "unknown"
            ),
        )

        try:
            if (
                sync_mode == "guild"
                and test_guild_id
            ):
                synced = await bot.tree.sync(
                    guild=discord.Object(
                        id=int(test_guild_id)
                    )
                )

                log.info(
                    "🔄 Synced %d commands "
                    "to guild %s",
                    len(synced),
                    test_guild_id,
                )

            else:
                synced = await bot.tree.sync()

                log.info(
                    "🔄 Synced %d commands globally",
                    len(synced),
                )

        except Exception:
            log.error(
                "Command sync failed:\n%s",
                traceback.format_exc(),
            )

    @bot.event
    async def on_disconnect() -> None:
        log.info(
            "WebSocket disconnected "
            "(will auto-reconnect)"
        )

    @bot.event
    async def on_resumed() -> None:
        log.info(
            "WebSocket session resumed"
        )

    @bot.event
    async def on_error(
        event: str,
        *args,
        **kwargs,
    ) -> None:
        log.error(
            "on_error event=%s\n%s",
            event,
            traceback.format_exc(),
        )

    @bot.event
    async def on_command_error(
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        log.warning(
            "Prefix command error: "
            "cmd=%s user=%s(%s) "
            "guild=%s(%s) err=%s",
            getattr(
                ctx.command,
                "qualified_name",
                None,
            ),
            getattr(
                ctx.author,
                "name",
                None,
            ),
            getattr(
                ctx.author,
                "id",
                None,
            ),
            getattr(
                ctx.guild,
                "name",
                None,
            ),
            getattr(
                ctx.guild,
                "id",
                None,
            ),
            repr(error),
        )

    @bot.event
    async def on_command_completion(
        ctx: commands.Context,
    ) -> None:
        log.info(
            "Prefix command done: "
            "cmd=%s user=%s(%s) "
            "guild=%s(%s)",
            getattr(
                ctx.command,
                "qualified_name",
                None,
            ),
            getattr(
                ctx.author,
                "name",
                None,
            ),
            getattr(
                ctx.author,
                "id",
                None,
            ),
            getattr(
                ctx.guild,
                "name",
                None,
            ),
            getattr(
                ctx.guild,
                "id",
                None,
            ),
        )

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        command_name = getattr(
            getattr(
                interaction,
                "command",
                None,
            ),
            "qualified_name",
            None,
        )

        ctx = await build_ctx_from_interaction(
            interaction
        )

        with use_log_context(ctx):
            log.warning(
                "Slash command error: "
                "cmd=%s err=%s",
                command_name,
                repr(error),
            )

    @bot.command()
    async def sync(
        ctx: commands.Context,
    ) -> None:
        synced = await bot.tree.sync()

        await ctx.send(
            f"✅ Synced {len(synced)} commands"
        )

        log.info(
            "Manual sync invoked by "
            "%s(%s) in guild %s(%s): "
            "%d commands",
            getattr(
                ctx.author,
                "name",
                None,
            ),
            getattr(
                ctx.author,
                "id",
                None,
            ),
            getattr(
                ctx.guild,
                "name",
                None,
            ),
            getattr(
                ctx.guild,
                "id",
                None,
            ),
            len(synced),
        )