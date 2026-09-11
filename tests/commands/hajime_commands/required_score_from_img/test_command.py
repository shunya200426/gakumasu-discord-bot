import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from commands.base_command import BaseCommand
from commands.hajime_commands.required_score.command import HajimeRequiredScoreCommand
from commands.hajime_commands.required_score_from_img.command import (
    HajimeRequiredScoreFromImgCommand,
)
from commands.hajime_commands.required_score_from_img.ui import (
    hajime_required_score_from_img_command,
)
from inference.result import (
    BonusOcrResult,
    DetectionResult,
    InferenceResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from models.hajime.required_score_from_img.params import (
    HajimeRequiredScoreFromImgParams,
)
from services.image_consent_service import ImageConsentResult
from services.inference_log_recorder import InferenceLogRecorder


def make_params(*, mode: str = "legend", boost: bool = False):
    schedule = SimpleNamespace(filename="schedule.png", read=AsyncMock())
    party = SimpleNamespace(filename="party.png", read=AsyncMock())
    mid_exam = SimpleNamespace(filename="score.png", read=AsyncMock())
    return HajimeRequiredScoreFromImgParams(
        mode=mode,
        vo_ability=0,
        da_ability=0,
        vi_ability=0,
        schedule_img=schedule,
        party_img=party,
        mid_exam_score=50000,
        mid_exam_score_img=mid_exam,
        character=None,
        is_boost_active=boost,
        target_grade=None,
        target_score=None,
        save_agree=None,
    )


def make_interaction():
    interaction = Mock()
    interaction.response = SimpleNamespace(
        send_message=AsyncMock(),
        defer=AsyncMock(),
    )
    interaction.followup = SimpleNamespace(send=AsyncMock())
    interaction.user = SimpleNamespace(id=1)
    interaction.guild_id = 2
    interaction.channel_id = 3
    interaction.client = SimpleNamespace()
    return interaction


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "boost"),
    [("legend", True), ("master", False)],
)
async def test_unsupported_request_stops_before_attachment_read(
    mode: str,
    boost: bool,
) -> None:
    interaction = make_interaction()
    params = make_params(mode=mode, boost=boost)

    await HajimeRequiredScoreFromImgCommand(interaction).execute(params)

    interaction.response.send_message.assert_awaited_once()
    params.schedule_img.read.assert_not_awaited()
    params.party_img.read.assert_not_awaited()
    params.mid_exam_score_img.read.assert_not_awaited()
    interaction.response.defer.assert_not_awaited()


def test_command_uses_base_command_without_required_score_command() -> None:
    assert issubclass(HajimeRequiredScoreFromImgCommand, BaseCommand)
    assert not issubclass(
        HajimeRequiredScoreFromImgCommand,
        HajimeRequiredScoreCommand,
    )


def test_command_does_not_import_legacy_ocr() -> None:
    source_directory = (
        Path(__file__).parents[4]
        / "commands/hajime_commands/required_score_from_img"
    )
    imported_modules = set()
    for path in source_directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )

    assert "ocr.core" not in imported_modules


def test_image_save_consent_is_optional() -> None:
    field = HajimeRequiredScoreFromImgParams.__dataclass_fields__["save_agree"]
    signature = inspect.signature(hajime_required_score_from_img_command.callback)

    assert field.default is None
    assert signature.parameters["画像ログ"].annotation == bool | None
    assert signature.parameters["画像ログ"].default is None


def test_archive_images_include_optional_mid_exam_image() -> None:
    params = make_params()

    images = HajimeRequiredScoreFromImgCommand._build_archive_images(
        params=params,
        schedule_bytes=b"schedule",
        party_bytes=b"party",
        mid_exam_bytes=b"score",
    )

    assert set(images) == {"schedule", "party", "score"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("consent", "expected_calls"), [(True, 1), (False, 0)])
async def test_input_images_are_saved_only_with_consent(
    consent: bool,
    expected_calls: int,
) -> None:
    interaction = make_interaction()
    command = HajimeRequiredScoreFromImgCommand(interaction)
    command._request_id = "request1"
    storage = Mock()
    storage.save_input_images = AsyncMock(
        return_value={"schedule": "schedule.png"}
    )
    command.get_image_storage_service = Mock(return_value=storage)

    paths = await command._save_input_images(
        interaction=interaction,
        consent_result=ImageConsentResult(
            previous=None,
            current=consent,
            changed=consent,
        ),
        images={"schedule": ("schedule.png", b"image")},
        metadata={"mode": "legend"},
    )

    assert storage.save_input_images.await_count == expected_calls
    assert paths == ({"schedule": "schedule.png"} if consent else {})


@pytest.mark.asyncio
async def test_export_and_log_paths_are_connected_for_every_inference() -> None:
    interaction = make_interaction()
    command = HajimeRequiredScoreFromImgCommand(interaction)
    command._request_id = "request1"
    export_service = Mock()
    export_service.save = AsyncMock(
        side_effect=["schedule.json", "party.json", "score.json"]
    )
    recorder = Mock()
    command.get_inference_export_service = Mock(return_value=export_service)
    command.get_inference_log_recorder = Mock(return_value=recorder)
    inference = InferenceResult(
        parameters=ParameterOcrResult(),
        bonuses=BonusOcrResult(),
        scores=ScoreOcrResult(),
        detections=(
            DetectionResult(
                class_name="vo_param",
                confidence=0.9,
                x1=1,
                y1=2,
                x2=3,
                y2=4,
            ),
        ),
    )
    items = [("schedule", inference), ("party", inference), ("score", inference)]

    export_paths = await command._export_inference_results(
        interaction=interaction,
        inference_items=items,
    )
    command._record_inference_results(
        interaction=interaction,
        inference_items=items,
        saved_input_paths={
            "schedule": "schedule.png",
            "party": "party.png",
            "score": "score.png",
        },
        saved_export_paths=export_paths,
        status="SUCCESS",
    )

    assert export_paths == {
        "schedule": "schedule.json",
        "party": "party.json",
        "score": "score.json",
    }
    assert export_service.save.await_count == 3
    assert recorder.save.call_count == 3
    for call, role in zip(recorder.save.call_args_list, ("schedule", "party", "score"), strict=True):
        assert call.kwargs["image_role"] == role
        assert call.kwargs["image_path"] == f"{role}.png"
        assert call.kwargs["export_path"] == f"{role}.json"
        assert call.kwargs["inference_result"].detections == inference.detections


def test_inference_log_recorder_saves_detection_with_no_crop_path() -> None:
    repository = Mock()
    repository.connection = MagicMock()
    repository.save_inference_log.return_value = 10
    detector = SimpleNamespace(model_name="model", model_format="onnx")
    recorder = InferenceLogRecorder(repository=repository, detector=detector)
    inference = InferenceResult(
        parameters=ParameterOcrResult(),
        bonuses=BonusOcrResult(),
        scores=ScoreOcrResult(),
        detections=(
            DetectionResult(
                class_name="vo_param",
                confidence=0.9,
                x1=1,
                y1=2,
                x2=3,
                y2=4,
            ),
        ),
    )

    recorder.save(
        request_id="request1",
        guild_id=1,
        channel_id=2,
        user_id=3,
        command_name="hajime_required_score_from_img",
        image_role="schedule",
        image_path="schedule.png",
        export_path="schedule.json",
        inference_result=inference,
        status="SUCCESS",
    )

    repository.save_detection_result.assert_called_once_with(
        inference_log_id=10,
        class_name="vo_param",
        confidence=0.9,
        x1=1,
        y1=2,
        x2=3,
        y2=4,
        crop_path=None,
    )
