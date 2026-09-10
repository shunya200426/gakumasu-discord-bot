import json
from pathlib import Path

import pytest

from inference.result import (
    BonusOcrResult,
    DetectionResult,
    InferenceResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from services.inference_export_service import (
    InferenceExportService,
)


def _build_inference_result() -> InferenceResult:
    return InferenceResult(
        parameters=ParameterOcrResult(
            vo=1500,
            da=1400,
            vi=1300,
            fans=50000,
            star=3,
        ),
        bonuses=BonusOcrResult(
            vo=12.5,
            da=10.0,
            vi=8.5,
            kirameki=20,
        ),
        scores=ScoreOcrResult(
            sum_score=60000,
            vo=20000,
            da=19000,
            vi=21000,
        ),
        detections=(
            DetectionResult(
                class_name="vo",
                confidence=0.98,
                x1=100,
                y1=200,
                x2=300,
                y2=260,
            ),
            DetectionResult(
                class_name="da",
                confidence=0.95,
                x1=110,
                y1=300,
                x2=310,
                y2=360,
            ),
        ),
        image_width=1125,
        image_height=2436,
        preprocess_ms=1.2,
        inference_ms=24.8,
        postprocess_ms=18.5,
        total_ms=44.5,
    )


@pytest.mark.asyncio
async def test_save_inference_result_json(
    tmp_path: Path,
) -> None:
    service = InferenceExportService(
        export_directory=tmp_path,
    )

    export_path = await service.save(
        guild_id=123456789,
        user_id=987654321,
        request_id="request-001",
        image_role="schedule",
        inference_result=_build_inference_result(),
    )

    saved_path = Path(export_path)

    assert saved_path.exists()
    assert saved_path.suffix == ".json"

    payload = json.loads(
        saved_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["request_id"] == "request-001"
    assert payload["image_role"] == "schedule"
    assert "exported_at" in payload


@pytest.mark.asyncio
async def test_saved_json_contains_inference_result(
    tmp_path: Path,
) -> None:
    service = InferenceExportService(
        export_directory=tmp_path,
    )

    export_path = await service.save(
        guild_id=123456789,
        user_id=987654321,
        request_id="request-002",
        image_role="schedule",
        inference_result=_build_inference_result(),
    )

    payload = json.loads(
        Path(export_path).read_text(
            encoding="utf-8",
        )
    )

    result = payload["result"]

    assert result["parameters"] == {
        "vo": 1500,
        "da": 1400,
        "vi": 1300,
        "fans": 50000,
        "star": 3,
    }

    assert result["bonuses"] == {
        "vo": 12.5,
        "da": 10.0,
        "vi": 8.5,
        "kirameki": 20,
    }

    assert result["scores"] == {
        "sum_score": 60000,
        "vo": 20000,
        "da": 19000,
        "vi": 21000,
    }

    assert result["image_width"] == 1125
    assert result["image_height"] == 2436

    assert result["preprocess_ms"] == 1.2
    assert result["inference_ms"] == 24.8
    assert result["postprocess_ms"] == 18.5
    assert result["total_ms"] == 44.5


@pytest.mark.asyncio
async def test_saved_json_contains_detections(
    tmp_path: Path,
) -> None:
    service = InferenceExportService(
        export_directory=tmp_path,
    )

    export_path = await service.save(
        guild_id=123456789,
        user_id=987654321,
        request_id="request-003",
        image_role="party",
        inference_result=_build_inference_result(),
    )

    payload = json.loads(
        Path(export_path).read_text(
            encoding="utf-8",
        )
    )

    detections = payload["result"]["detections"]

    assert len(detections) == 2

    assert detections[0] == {
        "class_name": "vo",
        "confidence": 0.98,
        "x1": 100,
        "y1": 200,
        "x2": 300,
        "y2": 260,
    }

    assert detections[1] == {
        "class_name": "da",
        "confidence": 0.95,
        "x1": 110,
        "y1": 300,
        "x2": 310,
        "y2": 360,
    }


@pytest.mark.asyncio
async def test_different_image_roles_use_different_files(
    tmp_path: Path,
) -> None:
    service = InferenceExportService(
        export_directory=tmp_path,
    )

    inference_result = _build_inference_result()

    schedule_path = await service.save(
        guild_id=123456789,
        user_id=987654321,
        request_id="request-004",
        image_role="schedule",
        inference_result=inference_result,
    )

    party_path = await service.save(
        guild_id=123456789,
        user_id=987654321,
        request_id="request-004",
        image_role="party",
        inference_result=inference_result,
    )

    assert schedule_path != party_path

    assert Path(schedule_path).exists()
    assert Path(party_path).exists()

    assert "_schedule.json" in schedule_path
    assert "_party.json" in party_path


@pytest.mark.asyncio
async def test_empty_request_id_raises_value_error(
    tmp_path: Path,
) -> None:
    service = InferenceExportService(
        export_directory=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="request_id must not be empty",
    ):
        await service.save(
            guild_id=123456789,
            user_id=987654321,
            request_id="",
            image_role="schedule",
            inference_result=_build_inference_result(),
        )