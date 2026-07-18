"""
画像保存への同意状態を解決するサービス。

同意状態の取得・変更と今回の保存可否の決定を担当し、
Discordへの通知や画像ファイルの保存は担当しない。
"""

from dataclasses import dataclass

from db.repositories.user_repository import UserRepository


@dataclass(
    slots=True,
    frozen=True,
)
class ImageConsentResult:
    """
    画像保存同意の解決結果。

    Attributes:
        previous:
            処理前にDBへ保存されていた同意状態。
        current:
            今回のコマンドで使用する保存可否。
        changed:
            DB上の同意状態を変更したか。
    """

    previous: bool | None
    current: bool
    changed: bool


class ImageConsentService:
    """
    画像保存への同意状態を取得・変更するService。
    """

    def __init__(
        self,
        user_repository: UserRepository,
    ) -> None:
        self._user_repository = user_repository

    def resolve(
        self,
        *,
        user_id: int,
        requested: bool | None,
    ) -> ImageConsentResult:
        """
        保存済み状態と指定値から今回の画像保存可否を決定する。

        指定値によってDB上の状態が変わる場合のみ更新し、
        その更新を独立したトランザクションとして確定する。
        """
        previous = (
            self._user_repository.get_image_save_consent(
                user_id
            )
        )

        if requested is None:
            return ImageConsentResult(
                previous=previous,
                current=(
                    previous
                    if previous is not None
                    else False
                ),
                changed=False,
            )

        if requested == previous:
            return ImageConsentResult(
                previous=previous,
                current=requested,
                changed=False,
            )

        with self._user_repository.connection:
            self._user_repository.set_image_save_consent(
                user_id,
                requested,
            )

        return ImageConsentResult(
            previous=previous,
            current=requested,
            changed=True,
        )
