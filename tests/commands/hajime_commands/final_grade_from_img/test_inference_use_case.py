from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest

import commands.hajime_commands.final_grade_from_img.inference_use_case as module
from commands.hajime_commands.final_grade_from_img.inference_use_case import (
    InferenceUseCase,
)
from inference.result import (
    BonusOcrResult,
    InferenceResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from models.hajime.final_grade.result import HajimeFinalGradeResult
from models.hajime.final_grade_from_img.params import HajimeFinalGradeFromImgParams

IMAGE = np.zeros((4, 4, 3), dtype=np.uint8)


def inference(vo=None, da=None, vi=None, score=None):
    return InferenceResult(
        ParameterOcrResult(vo, da, vi),
        BonusOcrResult(),
        ScoreOcrResult(sum_score=score),
        total_ms=1.5,
    )


def params(**updates):
    return replace(
        HajimeFinalGradeFromImgParams(
            "legend", 0, 0, 0, object(), object(), object(), 50000, "first"
        ),
        **updates,
    )


@pytest.fixture(autouse=True)
def inline_threads(monkeypatch):
    async def inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(module.asyncio, "to_thread", inline)


async def execute(results, *, mid=False, **updates):
    service = Mock()
    service.infer.side_effect = results
    use_case = InferenceUseCase(service)
    use_case.calculate = Mock(wraps=use_case.calculate)
    result = await use_case.execute(
        params=params(**updates),
        schedule_image=IMAGE,
        party_image=IMAGE,
        final_exam_image=IMAGE,
        mid_exam_image=IMAGE if mid else None,
    )
    return result, service, use_case


@pytest.mark.asyncio
@pytest.mark.parametrize("mid", [False, True])
async def test_input_source_party_missing_and_common_calculation(mid):
    results = [inference(1000, 1100, 1200), inference(), inference(score=300000)]
    if mid:
        results.append(inference(score=60000))
    result, service, use_case = await execute(results, mid=mid)
    assert result.success
    assert result.mid_exam_score == (60000 if mid else 50000)
    assert result.mid_exam_score_source == ("image" if mid else "manual")
    assert isinstance(result.final_grade_result, HajimeFinalGradeResult)
    assert result.party_inference is results[1]
    assert service.infer.call_count == (4 if mid else 3)
    assert all(
        call.kwargs["parameter_maximum"] == 3000
        for call in service.infer.call_args_list
    )
    use_case.calculate.assert_called_once()
    assert (
        result.schedule_inference_ms
        == result.party_inference_ms
        == result.final_exam_inference_ms
        == 1.5
    )
    assert result.mid_exam_inference_ms == (1.5 if mid else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["vo", "da", "vi"])
async def test_missing_parameters(missing):
    values = {"vo": 1000, "da": 1000, "vi": 1000}
    values[missing] = None
    result, _, use_case = await execute(
        [inference(**values), inference(), inference(score=123)]
    )
    assert result.failed_sections == ["parameters"]
    assert not result.success
    use_case.calculate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [None, -1, 200001])
async def test_mid_image_invalid_never_falls_back(score):
    result, _, use_case = await execute(
        [
            inference(1000, 1000, 1000),
            inference(),
            inference(score=123),
            inference(score=score),
        ],
        mid=True,
    )
    assert result.failed_sections == ["mid_exam_scores"]
    assert result.mid_exam_score == score
    assert result.mid_exam_score_source == "image"
    use_case.calculate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [None, -1, 1.5])
async def test_final_score_missing_or_invalid(score):
    result, _, use_case = await execute(
        [inference(1000, 1000, 1000), inference(), inference(score=score)]
    )
    assert result.failed_sections == ["final_exam_scores"]
    use_case.calculate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {"mode": "master"},
        {"is_boost_active": True},
        {"mid_exam_score": -1},
        {"mid_exam_score": 200001},
    ],
)
async def test_invalid_request_before_inference(updates):
    service = Mock()
    with pytest.raises((ValueError, NotImplementedError)):
        await InferenceUseCase(service).execute(
            params=params(**updates),
            schedule_image=IMAGE,
            party_image=IMAGE,
            final_exam_image=IMAGE,
            mid_exam_image=None,
        )
    service.infer.assert_not_called()


def calculation_values():
    return {
        "mode": "legend",
        "character": None,
        "vo_status": 1000,
        "da_status": 1000,
        "vi_status": 1000,
        "vo_ability": 0,
        "da_ability": 0,
        "vi_ability": 0,
        "mid_exam_score": 50000,
        "final_exam_score": 10**12,
        "final_exam_rank": "first",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("vo_status", None),
        ("vo_status", -1),
        ("vo_ability", -1),
        ("da_ability", 1.5),
        ("vi_ability", True),
        ("mid_exam_score", 200001),
        ("final_exam_score", -1),
        ("final_exam_rank", "invalid"),
    ],
)
def test_calculation_validates_values(key, value):
    service = Mock()
    with pytest.raises(ValueError):
        InferenceUseCase(service).calculate(**{**calculation_values(), key: value})
    service.infer.assert_not_called()


def test_final_score_has_no_upper_limit():
    result = InferenceUseCase(Mock()).calculate(**calculation_values())
    assert result.final_exam_score == 10**12
    assert result.is_boost_active is False
    assert result.kirameki == 0


@pytest.mark.asyncio
async def test_result_success_requires_all_conditions_and_lists_are_independent():
    result, _, _ = await execute(
        [inference(1000, 1000, 1000), inference(), inference(score=123)]
    )
    other = replace(result, failed_sections=[])
    result.failed_sections.append("parameters")
    assert not result.success
    assert other.success
    other.error_reason = "error"
    assert not other.success
    other.error_reason = None
    other.final_grade_result = None
    assert not other.success


@pytest.mark.asyncio
async def test_image_score_ignores_unused_invalid_manual_score():
    result, _, _ = await execute(
        [
            inference(1000, 1000, 1000),
            inference(),
            inference(score=123),
            inference(score=60000),
        ],
        mid=True,
        mid_exam_score=200001,
    )
    assert result.success
    assert result.mid_exam_score == 60000
