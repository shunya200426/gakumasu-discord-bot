# Standard library
import time
import zoneinfo
from collections.abc import Hashable
from datetime import datetime

# Third-party
import discord
from discord import ui
from discord.ext import commands

# Local application
from utils.logger import get_logger

log = get_logger()


class SimpleRateLimiter:
    def __init__(self):
        self._next_ok: dict[Hashable, float] = {}

    def allow(
        self,
        key: Hashable,
        interval_sec: float,
    ) -> bool:
        now = time.monotonic()
        nxt = self._next_ok.get(key, 0.0)

        if now >= nxt:
            self._next_ok[key] = now + interval_sec
            return True

        return False

    def remaining(
        self,
        key: Hashable,
    ) -> float:
        now = time.monotonic()
        nxt = self._next_ok.get(key, 0.0)

        return max(0.0, nxt - now)


_rate_limiter = SimpleRateLimiter()


async def notify_dev_about_block(
    bot: commands.Bot,
    reason: str,
    interaction: discord.Interaction,
    *,
    dev_user_id: int,
    alert_channel_id: int,
    cooldown_per_guild: int,
    cooldown_per_user: int,
    cooldown_global: int,
) -> None:
    """
    未登録・停止・DM実行などのアクセス拒否を検知した際、
    開発者へ通知する。

    レートリミットで通知スパムを防止し、
    DM送信に失敗した場合はAlert Channelへフォールバックする。
    """

    # ====== レートリミット ======
    if not _rate_limiter.allow(
        ("devdm:global", "any"),
        cooldown_global,
    ):
        log.debug(
            "Skip dev DM (global cooldown active)"
        )
        return

    guild = interaction.guild
    user = interaction.user
    channel = interaction.channel

    guild_id = getattr(
        guild,
        "id",
        None,
    )
    user_id = getattr(
        user,
        "id",
        None,
    )

    if (
        guild_id is not None
        and not _rate_limiter.allow(
            ("devdm:guild", guild_id),
            cooldown_per_guild,
        )
    ):
        log.debug(
            "Skip dev DM "
            "(guild cooldown active) gid=%s",
            guild_id,
        )
        return

    if (
        user_id is not None
        and not _rate_limiter.allow(
            ("devdm:user", user_id),
            cooldown_per_user,
        )
    ):
        log.debug(
            "Skip dev DM "
            "(user cooldown active) uid=%s",
            user_id,
        )
        return

    # ====== 開発者ID確認 ======
    if not dev_user_id:
        log.warning(
            "DEV_USER_ID is not set; "
            "skip developer DM."
        )
        return

    # ====== 通知内容生成 ======
    jst = zoneinfo.ZoneInfo(
        "Asia/Tokyo"
    )
    now_jst = datetime.now(jst)

    timestamp = now_jst.strftime(
        "%Y-%m-%d %H:%M:%S JST"
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

    lines = [
        "# 【Bot警告】",
        (
            "### 未許可実行を検知"
            f"__（{reason}）__"
        ),
        "### 時刻: ",
        f"**{timestamp}**",
        "### コマンド: ",
        (
            f"</{command_name}:"
            "1417467125567848458>"
        ),
        "### 実行者: ",
        (
            "**__`"
            f"{getattr(user, 'name', None)}"
            "`__ "
            f"({getattr(user, 'id', None)})**"
        ),
        "### サーバー: ",
        (
            "**__"
            f"{getattr(guild, 'name', '(DM/不明)')}"
            "__ "
            f"({getattr(guild, 'id', None)})**"
        ),
        "### チャンネル: ",
        (
            "**"
            f"{getattr(channel, 'name', None)} "
            f"({getattr(channel, 'id', None)})"
            "**"
        ),
    ]

    content = "\n".join(lines)

    # ====== Discord Components V2 ======
    view = ui.LayoutView()

    container = ui.Container(
        accent_color=0xE53935
    )
    container.add_item(
        ui.TextDisplay(content)
    )

    view.add_item(container)

    # ====== 開発者DM ======
    try:
        dev_user = (
            bot.get_user(dev_user_id)
            or await bot.fetch_user(
                dev_user_id
            )
        )

        if not dev_user:
            raise RuntimeError(
                "developer user not found"
            )

        dm = (
            dev_user.dm_channel
            or await dev_user.create_dm()
        )

        await dm.send(
            content=" ",
            view=view,
        )

        log.info(
            "Developer DM sent "
            "for blocked use (%s).",
            reason,
        )

        return

    except Exception:
        log.exception(
            "Failed to DM developer for blocked use."
        )

    # ====== Alert Channelへフォールバック ======
    if alert_channel_id:
        try:
            alert_channel = bot.get_channel(
                alert_channel_id
            )

            if alert_channel:
                await alert_channel.send(
                    content
                )

                log.info(
                    "Alert posted to "
                    "ALERT_CHANNEL_ID "
                    "as fallback."
                )

        except Exception:
            log.exception(
                "Failed to post to alert channel as fallback."
            )