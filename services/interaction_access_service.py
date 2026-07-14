# Standard library
from dataclasses import dataclass
from enum import Enum

# Third-party
import discord

# Local application
from db.repositories.guild_repository import GuildRepository
from db.repositories.user_repository import UserRepository


class AccessDeniedReason(Enum):
    """
    コマンド実行を拒否した理由。
    """

    USER_BLOCKED = "user_blocked"
    DM_NOT_ALLOWED = "dm"
    GUILD_NOT_REGISTERED = "unregistered"
    GUILD_DISABLED = "revoked"


@dataclass(frozen=True)
class InteractionAccessResult:
    """
    アクセス判定結果。
    """
    allowed: bool
    denied_reason: AccessDeniedReason | None = None
    user_message: str | None = None
    internal_reason: str | None = None


class InteractionAccessService:
    """
    Discord Interactionのアクセス可否を判定するService。
    """

    def __init__(
        self,
        guild_repository: GuildRepository,
        user_repository: UserRepository,
    ) -> None:
        self.guild_repository = guild_repository
        self.user_repository = user_repository


    def check_access(
        self,
        interaction: discord.Interaction,
    ) -> InteractionAccessResult:
        """
        Interactionのアクセス可否を判定する。
        """
        connection = self.user_repository.connection

        with connection:
            guild_id = interaction.guild_id

            user_id = self._upsert_user(
                interaction
            )

            result = self._check_user_block(
                user_id
            )
            if result is not None:
                return result

            result = self._check_dm(
                guild_id
            )
            if result is not None:
                return result

            result = self._check_guild(
                guild_id
            )
            if result is not None:
                return result

            return InteractionAccessResult(
                allowed=True,
            )


    def _upsert_user(
        self,
        interaction: discord.Interaction,
    ) -> int:
        """
        Interactionのユーザー情報をDBへ登録・更新する。

        Returns:
            DiscordユーザーID。

        Raises:
            ValueError:
                InteractionからユーザーIDを取得できない場合。
        """
        user = interaction.user

        user_id = getattr(
            user,
            "id",
            None,
        )

        if user_id is None:
            # Discord Interactionでは通常発生しない。
            # 発生した場合は内部異常として処理を中断する。
            raise ValueError(
                "Interactionからuser_idを取得できません。"
            )

        self.user_repository.upsert_user(
            user_id=user_id,
            user_name=getattr(
                user,
                "name",
                None,
            ),
            display_name=getattr(
                user,
                "display_name",
                None,
            ),
        )

        return user_id
    

    def _check_user_block(
        self,
        user_id: int,
    ) -> InteractionAccessResult | None:
        """
        ユーザーがブロックされているか確認する。
        """
        block_info = self.user_repository.get_block(
            user_id
        )

        if block_info is None:
            return None

        return InteractionAccessResult(
            allowed=False,
            denied_reason=AccessDeniedReason.USER_BLOCKED,
            user_message=(
                block_info["user_message"]
            ),
            internal_reason=(
                block_info["reason"]
                or "理由未設定"
            ),
        )
    

    def _check_dm(
        self,
        guild_id: int | None,
    ) -> InteractionAccessResult | None:
        """
        DMから実行されたか確認する。
        """
        if guild_id is not None:
            return None

        return InteractionAccessResult(
            allowed=False,
            denied_reason=AccessDeniedReason.DM_NOT_ALLOWED,
        )


    def _check_guild(
        self,
        guild_id: int,
    ) -> InteractionAccessResult | None:
        """
        サーバーが登録済みか確認する
        """
        guild_info = (
            self.guild_repository.get_by_guild_id(
                guild_id
            )
        )

        if guild_info is None:
            return InteractionAccessResult(
                allowed=False,
                denied_reason=AccessDeniedReason.GUILD_NOT_REGISTERED,
            )

        if not guild_info["enabled"]:
            return InteractionAccessResult(
                allowed=False,
                denied_reason=AccessDeniedReason.GUILD_DISABLED,
            )

        return None