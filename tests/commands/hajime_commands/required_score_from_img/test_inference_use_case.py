from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest

import commands.hajime_commands.required_score_from_img.inference_use_case as use_case_module
from commands.hajime_commands.required_score.calculator import (
    BoostModeNotSupportedError,
    RequiredScoreCalculator,
)
from commands.hajime_commands.required_score_from_img.inference_use_case import (
    InferenceUseCase,
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

IMAGE = np.zeros((4, 4, 3), dtype=np.uint8)


@pytest.fixture(autouse=True)
def run_to_thread_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(use_case_module.asyncio, "to_thread", inline)


class StubInferenceService:
    def __init__(self, results: list[InferenceResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[np.ndarray, int]] = []

    def infer(
        self,
        image: np.ndarray,
        *,
        parameter_maximum: int,
    ) -> InferenceResult:
        self.calls.append((image, parameter_maximum))
        return self.results.pop(0)


def make_inference(
    *,
    vo: int | None = None,
    da: int | None = None,
    vi: int | None = None,
    bonus_vo: float | None = None,
    bonus_da: float | None = None,
    bonus_vi: float | None = None,
    sum_score: int | None = None,
    detection_name: str = "test",
) -> InferenceResult:
    return InferenceResult(
        parameters=ParameterOcrResult(vo=vo, da=da, vi=vi),
        bonuses=BonusOcrResult(
            vo=bonus_vo,
            da=bonus_da,
            vi=bonus_vi,
        ),
        scores=ScoreOcrResult(sum_score=sum_score),
        detections=(
            DetectionResult(
                class_name=detection_name,
                confidence=0.9,
                x1=1,
                y1=1,
                x2=3,
                y2=3,
            ),
        ),
        total_ms=1.5,
    )


@pytest.fixture
def params() -> HajimeRequiredScoreFromImgParams:
    return HajimeRequiredScoreFromImgParams(
        mode="legend",
        vo_ability=0,
        da_ability=0,
        vi_ability=0,
        schedule_img=object(),
        party_img=object(),
        mid_exam_score=50000,
        mid_exam_score_img=None,
        character=None,
        is_boost_active=False,
        target_grade="SS",
        target_score=None,
        save_agree=None,
    )


@pytest.mark.asyncio
async def test_manual_mid_exam_score_and_party_missing_ocr_are_accepted(
    params: HajimeRequiredScoreFromImgParams,
) -> None:
    schedule = make_inference(vo=1000, da=1000, vi=1000, detection_name="vo_param")
    party = make_inference(detection_name="unrelated")
    service = StubInferenceService([schedule, party])

    result = await InferenceUseCase(service).execute(
        params=params,
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=None,
    )

    assert result.success
    assert len(service.calls) == 2
    assert result.mid_exam_score == 50000
    assert result.mid_exam_score_source == "manual"
    assert result.mid_exam_inference is None
    assert result.party_inference is party
    assert result.bonuses == {
        "vo": None,
        "da": None,
        "vi": None,
        "kirameki": None,
    }


@pytest.mark.asyncio
async def test_mid_exam_image_score_takes_priority(
    params: HajimeRequiredScoreFromImgParams,
) -> None:
    schedule = make_inference(vo=1000, da=1000, vi=1000)
    party = make_inference()
    mid_exam = make_inference(sum_score=60000, detection_name="exam_score")
    service = StubInferenceService([schedule, party, mid_exam])

    result = await InferenceUseCase(service).execute(
        params=replace(params, mid_exam_score=12345),
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=IMAGE,
    )

    assert result.success
    assert len(service.calls) == 3
    assert result.mid_exam_score == 60000
    assert result.mid_exam_score_source == "image"
    assert result.mid_exam_inference is mid_exam


@pytest.mark.asyncio
async def test_mid_exam_ocr_failure_does_not_fall_back_to_manual_value(
    params: HajimeRequiredScoreFromImgParams,
) -> None:
    service = StubInferenceService(
        [
            make_inference(vo=1000, da=1000, vi=1000),
            make_inference(),
            make_inference(sum_score=None),
        ]
    )

    result = await InferenceUseCase(service).execute(
        params=params,
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=IMAGE,
    )

    assert not result.success
    assert result.mid_exam_score is None
    assert result.mid_exam_score_source == "image"
    assert result.failed_sections == ["scores"]
    assert result.required_score_result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [-1, 200001])
async def test_mid_exam_ocr_score_out_of_range_is_error(
    params: HajimeRequiredScoreFromImgParams,
    score: int,
) -> None:
    service = StubInferenceService(
        [
            make_inference(vo=1000, da=1000, vi=1000),
            make_inference(),
            make_inference(sum_score=score),
        ]
    )

    result = await InferenceUseCase(service).execute(
        params=params,
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=IMAGE,
    )

    assert not result.success
    assert result.failed_sections == ["scores"]
    assert result.required_score_result is None


@pytest.mark.asyncio
async def test_manual_mid_exam_score_out_of_range_stops_before_inference(
    params: HajimeRequiredScoreFromImgParams,
) -> None:
    service = StubInferenceService([])

    with pytest.raises(ValueError, match="0～200000"):
        await InferenceUseCase(service).execute(
            params=replace(params, mid_exam_score=200001),
            schedule_image=IMAGE,
            party_image=IMAGE,
            mid_exam_image=None,
        )

    assert service.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_parameter", ["vo", "da", "vi"])
async def test_missing_schedule_parameter_is_error(
    params: HajimeRequiredScoreFromImgParams,
    missing_parameter: str,
) -> None:
    schedule_parameters = {"vo": 1000, "da": 1000, "vi": 1000}
    schedule_parameters[missing_parameter] = None
    service = StubInferenceService(
        [make_inference(**schedule_parameters), make_inference()]
    )

    result = await InferenceUseCase(service).execute(
        params=params,
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=None,
    )

    assert not result.success
    assert len(service.calls) == 2
    assert result.failed_sections == ["parameters"]
    assert result.required_score_result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "boost", "exception_type"),
    [
        ("legend", True, BoostModeNotSupportedError),
        ("master", False, ValueError),
    ],
)
async def test_unsupported_request_stops_before_inference(
    params: HajimeRequiredScoreFromImgParams,
    mode: str,
    boost: bool,
    exception_type: type[Exception],
) -> None:
    service = StubInferenceService([])

    with pytest.raises(exception_type):
        await InferenceUseCase(service).execute(
            params=replace(params, mode=mode, is_boost_active=boost),
            schedule_image=IMAGE,
            party_image=IMAGE,
            mid_exam_image=None,
        )

    assert service.calls == []


@pytest.mark.asyncio
async def test_required_score_calculator_is_reused(
    params: HajimeRequiredScoreFromImgParams,
) -> None:
    schedule = make_inference(vo=1000, da=1000, vi=1000)
    party = make_inference()
    service = StubInferenceService([schedule, party])
    calculator = Mock(spec=RequiredScoreCalculator)
    calculator.compute_required_result_dict.return_value = {"SS": 123400}
    calculator.build_pairs.return_value = ([("**SS**", "123400")], "SS", None)

    result = await InferenceUseCase(service, calculator=calculator).execute(
        params=params,
        schedule_image=IMAGE,
        party_image=IMAGE,
        mid_exam_image=None,
    )

    calculator.compute_required_result_dict.assert_called_once()
    calculator.build_pairs.assert_called_once()
    assert result.required_score_result is not None
    assert result.required_score_result.SS_required_score == 123400
    assert result.pairs == [("**SS**", "123400")]
