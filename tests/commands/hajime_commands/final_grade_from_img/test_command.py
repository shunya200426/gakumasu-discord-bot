import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from commands.base_command import BaseCommand
from commands.hajime_commands.final_grade_from_img.command import (
    HajimeFinalGradeFromImgCommand,
)
from commands.hajime_commands.final_grade_from_img.ui import (
    hajime_final_grade_from_img_command,
)
from commands.hajime_commands.required_score.command import HajimeRequiredScoreCommand
from inference.result import (
    BonusOcrResult,
    DetectionResult,
    InferenceResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from models.hajime.final_grade_from_img.params import (
    HajimeFinalGradeFromImgParams,
)
from services.image_consent_service import ImageConsentResult


def make_params(*, mode: str = "legend", boost: bool = False):
    schedule = SimpleNamespace(filename="schedule.png", read=AsyncMock())
    party = SimpleNamespace(filename="party.png", read=AsyncMock())
    mid_exam = SimpleNamespace(filename="score.png", read=AsyncMock())
    return HajimeFinalGradeFromImgParams(
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
        final_exam_score_img=SimpleNamespace(filename="final.png", read=AsyncMock()),
        final_exam_rank="first",
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

    await HajimeFinalGradeFromImgCommand(interaction).execute(params)

    interaction.response.send_message.assert_awaited_once()
    params.schedule_img.read.assert_not_awaited()
    params.party_img.read.assert_not_awaited()
    params.final_exam_score_img.read.assert_not_awaited()
    params.mid_exam_score_img.read.assert_not_awaited()
    interaction.response.defer.assert_not_awaited()


def test_command_uses_base_command_without_required_score_command() -> None:
    assert issubclass(HajimeFinalGradeFromImgCommand, BaseCommand)
    assert not issubclass(
        HajimeFinalGradeFromImgCommand,
        HajimeRequiredScoreCommand,
    )


def test_command_does_not_import_legacy_ocr() -> None:
    source_directory = (
        Path(__file__).parents[4] / "commands/hajime_commands/final_grade_from_img"
    )
    imported_modules = set()
    for path in source_directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules.update(
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )

    assert "ocr.core" not in imported_modules


def test_image_save_consent_is_optional() -> None:
    field = HajimeFinalGradeFromImgParams.__dataclass_fields__["save_agree"]
    signature = inspect.signature(hajime_final_grade_from_img_command.callback)

    assert field.default is None
    assert signature.parameters["画像ログ"].annotation == bool | None
    assert signature.parameters["画像ログ"].default is None


def test_archive_images_include_optional_mid_exam_image() -> None:
    params = make_params()

    images = HajimeFinalGradeFromImgCommand._build_archive_images(
        params=params,
        schedule_bytes=b"schedule",
        party_bytes=b"party",
        final_exam_bytes=b"final",
        mid_exam_bytes=b"score",
    )

    assert set(images) == {"schedule", "party", "mid_exam_score", "final_exam_score"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("consent", "expected_calls"), [(True, 1), (False, 0)])
async def test_input_images_are_saved_only_with_consent(
    consent: bool,
    expected_calls: int,
) -> None:
    interaction = make_interaction()
    command = HajimeFinalGradeFromImgCommand(interaction)
    command._request_id = "request1"
    storage = Mock()
    storage.save_input_images = AsyncMock(return_value={"schedule": "schedule.png"})
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
    command = HajimeFinalGradeFromImgCommand(interaction)
    command._request_id = "request1"
    export_service = Mock()
    export_service.save = AsyncMock(
        side_effect=[
            "schedule.json",
            "party.json",
            "mid_exam_score.json",
            "final_exam_score.json",
        ]
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
    items = [
        (role, inference)
        for role in ("schedule", "party", "mid_exam_score", "final_exam_score")
    ]

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
            "mid_exam_score": "mid_exam_score.png",
            "final_exam_score": "final_exam_score.png",
        },
        saved_export_paths=export_paths,
        status="SUCCESS",
    )

    assert export_paths == {
        "schedule": "schedule.json",
        "party": "party.json",
        "mid_exam_score": "mid_exam_score.json",
        "final_exam_score": "final_exam_score.json",
    }
    assert export_service.save.await_count == 4
    assert recorder.save.call_count == 4
    for call, role in zip(
        recorder.save.call_args_list,
        ("schedule", "party", "mid_exam_score", "final_exam_score"),
        strict=True,
    ):
        assert call.kwargs["image_role"] == role
        assert call.kwargs["image_path"] == f"{role}.png"
        assert call.kwargs["export_path"] == f"{role}.json"
        assert call.kwargs["inference_result"].detections == inference.detections


from dataclasses import replace

import cv2
import numpy as np

from commands.hajime_commands.final_grade_from_img.command import (
    FinalExamRankSelect,
    ParamEditModal,
    ParamSelect,
)
from commands.hajime_commands.final_grade_from_img.inference_use_case import (
    InferenceUseCase,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mid", [False, True])
@pytest.mark.parametrize("missing", [False, True])
async def test_execute_reads_images_and_displays_controls(mid, missing):
    interaction = make_interaction()
    interaction.edit_original_response = AsyncMock()
    interaction.original_response = AsyncMock()
    params = make_params()
    if not mid:
        params = replace(params, mid_exam_score_img=None)
    encoded = cv2.imencode(".png", np.zeros((4, 4, 3), dtype=np.uint8))[1].tobytes()
    for attachment in (
        params.schedule_img,
        params.party_img,
        params.final_exam_score_img,
        params.mid_exam_score_img,
    ):
        if attachment is not None:
            attachment.content_type = "image/png"
            attachment.size = len(encoded)
            attachment.read.return_value = encoded

    def inference(score=None, schedule=False):
        return InferenceResult(
            parameters=ParameterOcrResult(
                vo=None if missing else 1000, da=1000, vi=1000
            )
            if schedule
            else ParameterOcrResult(),
            bonuses=BonusOcrResult(),
            scores=ScoreOcrResult(sum_score=score),
        )

    service = Mock()
    service.infer.side_effect = [
        inference(schedule=True),
        inference(),
        inference(score=12345),
    ] + ([inference(score=60000)] if mid else [])
    interaction.client.inference_service = service
    command = HajimeFinalGradeFromImgCommand(interaction)
    command.resolve_image_consent = Mock(
        return_value=ImageConsentResult(False, False, False)
    )
    command._export_inference_results = AsyncMock(return_value={})
    command._record_inference_results = Mock()
    command.send_image_consent_notification = AsyncMock()
    await command.execute(params)
    for attachment in (
        params.schedule_img,
        params.party_img,
        params.final_exam_score_img,
    ):
        attachment.read.assert_awaited_once()
    if mid:
        params.mid_exam_score_img.read.assert_awaited_once()
    assert service.infer.call_count == (4 if mid else 3)
    assert command._current_values["mid_exam_score"] == (60000 if mid else 50000)
    assert command._current_values["vo_status"] == (None if missing else 1000)
    view = interaction.edit_original_response.call_args.kwargs["view"]
    assert any(isinstance(item, ParamSelect) for item in view.walk_children())
    assert any(isinstance(item, FinalExamRankSelect) for item in view.walk_children())
    assert len(command._inference_items(command._use_case_result)) == (4 if mid else 3)
    command.send_image_consent_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_modal_and_rank_recalculate_without_inference():
    interaction = make_interaction()
    make_params()
    command = HajimeFinalGradeFromImgCommand(interaction)
    command._static = {
        "mode": "legend",
        "character": None,
        "is_boost_active": False,
        "kirameki": 0,
    }
    command._current_values = {
        "vo_status": 1000,
        "da_status": 1000,
        "vi_status": 1000,
        "vo_ability": 0,
        "da_ability": 0,
        "vi_ability": 0,
        "mid_exam_score": 50000,
        "final_exam_score": 12345,
        "final_exam_rank": "first",
    }
    command._use_case_result = SimpleNamespace(mid_exam_score_source="manual")
    service = Mock()
    use_case = InferenceUseCase(service)
    use_case.calculate = Mock(wraps=use_case.calculate)
    command._get_inference_use_case = Mock(return_value=use_case)
    select = ParamSelect(command)
    assert len(select.options) == 8
    assert select.max_values == 5
    modal = ParamEditModal(
        command,
        ["Vo試験終了時アビ", "Da試験終了時アビ", "Vi試験終了時アビ"],
        command._current_values,
    )
    for label, value in (
        ("Vo試験終了時アビ", "100"),
        ("Da試験終了時アビ", "200"),
        ("Vi試験終了時アビ", "300"),
    ):
        modal.inputs[label]._value = value
    await modal.on_submit(interaction)
    assert use_case.calculate.call_args.kwargs["vo_ability"] == 100
    assert use_case.calculate.call_args.kwargs["da_ability"] == 200
    assert use_case.calculate.call_args.kwargs["vi_ability"] == 300
    rank = FinalExamRankSelect(command)
    rank._values = ["second"]
    await rank.callback(interaction)
    assert use_case.calculate.call_count == 2
    assert use_case.calculate.call_args.kwargs["final_exam_rank"] == "second"
    service.infer.assert_not_called()


@pytest.mark.asyncio
async def test_partial_corrections_preserve_missing_values():
    command = HajimeFinalGradeFromImgCommand(make_interaction())
    command._static = {"mode": "legend", "character": None}
    command._current_values = {
        "vo_status": None,
        "da_status": None,
        "vi_status": None,
        "mid_exam_score": None,
        "final_exam_score": None,
        "vo_ability": 0,
        "da_ability": 0,
        "vi_ability": 0,
        "final_exam_rank": "first",
    }
    use_case = InferenceUseCase(Mock())
    use_case.calculate = Mock(wraps=use_case.calculate)
    command._get_inference_use_case = Mock(return_value=use_case)
    await command._recompute_and_edit(
        command.interaction, {**command._current_values, "vo_status": "1000"}
    )
    assert command._current_values["vo_status"] == 1000
    assert command._current_values["final_exam_score"] is None
    use_case.calculate.assert_not_called()


@pytest.fixture(autouse=True)
def run_inference_thread_inline(monkeypatch):
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        "commands.hajime_commands.final_grade_from_img.inference_use_case.asyncio.to_thread",
        inline,
    )


def test_slash_choices_required_arguments_and_loader():
    from bot.command_loader import MODULES
    from config.character_settings import CHARACTERS

    command = hajime_final_grade_from_img_command
    fields = {field.name: field for field in command.parameters}
    assert command.description == "最終評価を画像から計算します"
    assert {field.name for field in command.parameters if field.required} == {
        "難易度",
        "スケジュール画面",
        "編成画面",
        "最終試験スコア画面",
        "最終試験順位",
    }
    assert [choice.value for choice in fields["難易度"].choices] == ["legend"]
    assert [choice.value for choice in fields["最終試験順位"].choices] == [
        "first",
        "second",
        "third",
        "other",
    ]
    assert [choice.value for choice in fields["キャラクター"].choices] == list(
        CHARACTERS
    )
    assert fields["中間試験スコア"].default == 50000
    assert "commands.hajime_commands.final_grade_from_img.ui" in MODULES


@pytest.mark.asyncio
async def test_invalid_modal_does_not_change_current_values():
    command = HajimeFinalGradeFromImgCommand(make_interaction())
    command._current_values = {"vo_ability": 0}
    command._recompute_and_edit = AsyncMock()
    modal = ParamEditModal(command, ["Vo試験終了時アビ"], command._current_values)
    modal.inputs["Vo試験終了時アビ"]._value = "invalid"
    await modal.on_submit(command.interaction)
    command._recompute_and_edit.assert_not_awaited()
    assert command._current_values == {"vo_ability": 0}
    assert command.interaction.followup.send.call_args.kwargs["ephemeral"] is True
