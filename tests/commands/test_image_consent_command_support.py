"""画像付きコマンドの同意解決・UI連携テスト。"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from commands.base_command import BaseCommand
from commands.nia_commands.final_grade_from_img.ui import (
    nia_final_grade_from_img_command,
)
from commands.nia_commands.required_score_from_img.ui import (
    nia_required_score_from_img_command,
)
from models.nia.final_grade_from_img.params import (
    NiaFinalGradeFromImgParams,
)
from models.nia.required_score_from_img.params import (
    NiaRequiredScoreFromImgParams,
)
from services.image_consent_service import ImageConsentResult


PROJECT_DIR = Path(__file__).resolve().parents[2]


class DummyCommand(BaseCommand):
    """BaseCommandの同意共通処理を検証する具象クラス。"""

    async def execute(self) -> None:
        return None


def build_interaction(
    result: ImageConsentResult,
) -> tuple[Mock, Mock]:
    service = Mock()
    service.resolve.return_value = result

    interaction = Mock()
    interaction.client = SimpleNamespace(
        image_consent_service=service,
    )
    interaction.user.id = 123
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()

    return interaction, service


@pytest.mark.parametrize(
    "requested",
    [None, True, False],
)
def test_resolve_image_consent_passes_requested_value(
    requested: bool | None,
) -> None:
    expected = ImageConsentResult(
        previous=None,
        current=bool(requested),
        changed=False,
    )
    interaction, service = build_interaction(expected)
    command = DummyCommand(interaction)

    actual = asyncio.run(
        command.resolve_image_consent(
            interaction=interaction,
            requested=requested,
        )
    )

    assert actual is expected
    service.resolve.assert_called_once_with(
        user_id=123,
        requested=requested,
    )
    interaction.followup.send.assert_not_called()
    assert not hasattr(command, "_image_consent_result")


@pytest.mark.parametrize(
    ("result", "expected_message"),
    [
        (
            ImageConsentResult(None, False, False),
            None,
        ),
        (
            ImageConsentResult(None, True, True),
            (
                "画像保存へのご協力ありがとうございます！\n"
                "今後は設定を変更するまで、入力画像および"
                "推論・切り抜き画像を保存します。"
            ),
        ),
        (
            ImageConsentResult(None, False, True),
            (
                "画像保存を無効にしました。\n"
                "今回以降の入力画像および推論・切り抜き画像は"
                "保存されません。"
            ),
        ),
        (
            ImageConsentResult(True, True, False),
            None,
        ),
        (
            ImageConsentResult(True, False, True),
            (
                "画像保存を無効にしました。\n"
                "今回以降の入力画像および推論・切り抜き画像は"
                "保存されません。"
            ),
        ),
        (
            ImageConsentResult(False, False, False),
            None,
        ),
        (
            ImageConsentResult(False, True, True),
            (
                "画像保存へのご協力ありがとうございます！\n"
                "今後は設定を変更するまで、入力画像および"
                "推論・切り抜き画像を保存します。"
            ),
        ),
    ],
)
def test_resolve_image_consent_notifies_only_when_changed(
    result: ImageConsentResult,
    expected_message: str | None,
) -> None:
    interaction, _ = build_interaction(result)
    command = DummyCommand(interaction)

    asyncio.run(
        command.resolve_image_consent(
            interaction=interaction,
            requested=result.current,
        )
    )

    if expected_message is None:
        interaction.followup.send.assert_not_called()
    else:
        interaction.followup.send.assert_awaited_once_with(
            content=expected_message,
            embed=None,
            view=None,
            ephemeral=True,
        )


def test_notification_failure_does_not_discard_consent_result() -> None:
    expected = ImageConsentResult(
        previous=False,
        current=True,
        changed=True,
    )
    interaction, _ = build_interaction(expected)
    interaction.followup.send.side_effect = RuntimeError(
        "notification failed"
    )
    command = DummyCommand(interaction)

    actual = asyncio.run(
        command.resolve_image_consent(
            interaction=interaction,
            requested=True,
        )
    )

    assert actual is expected
    interaction.followup.send.assert_awaited_once()


@pytest.mark.parametrize(
    "slash_command",
    [
        nia_final_grade_from_img_command,
        nia_required_score_from_img_command,
    ],
)
def test_image_command_has_optional_consent_argument(
    slash_command: object,
) -> None:
    signature = inspect.signature(
        slash_command.callback
    )
    parameter = signature.parameters["画像保存"]

    assert parameter.annotation == bool | None
    assert parameter.default is None

    discord_parameter = next(
        item
        for item in slash_command.parameters
        if item.name == "画像保存"
    )
    assert discord_parameter.required is False


def test_image_params_keep_requested_consent_separate() -> None:
    final_field = (
        NiaFinalGradeFromImgParams.__dataclass_fields__[
            "image_save_consent"
        ]
    )
    required_field = (
        NiaRequiredScoreFromImgParams.__dataclass_fields__[
            "image_save_consent"
        ]
    )

    assert final_field.default is None
    assert required_field.default is None


@pytest.mark.parametrize(
    "relative_path",
    [
        "commands/nia_commands/final_grade_from_img/command.py",
        "commands/nia_commands/required_score_from_img/command.py",
    ],
)
def test_command_uses_local_consent_result(
    relative_path: str,
) -> None:
    source = (PROJECT_DIR / relative_path).read_text(
        encoding="utf-8"
    )

    assert "consent_result =" in source
    assert "params.image_save_consent" in source
    assert "consent_result.current" in source
    assert "self._image_consent_result" not in source


def test_text_commands_do_not_have_image_consent_argument() -> None:
    for relative_path in (
        "commands/nia_commands/final_grade/ui.py",
        "commands/nia_commands/required_score/ui.py",
    ):
        source = (PROJECT_DIR / relative_path).read_text(
            encoding="utf-8"
        )
        assert "画像保存" not in source
        assert "image_save_consent" not in source
