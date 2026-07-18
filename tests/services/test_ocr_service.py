from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pytest

from inference.result import (
    BonusOcrResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from ocr.tesseract_engine import TesseractEngine
from services.ocr_service import OcrService


@pytest.fixture
def engine() -> Mock:
    """
    TesseractEngineのモックを作成する。
    """
    return Mock(spec=TesseractEngine)


@pytest.fixture
def service(engine: Mock) -> OcrService:
    """
    テスト対象のOcrServiceを作成する。
    """
    return OcrService(engine)


@pytest.fixture
def dummy_image() -> np.ndarray:
    """
    OCR対象として使用するダミーBGR画像を作成する。
    """
    return np.full(
        (20, 60, 3),
        255,
        dtype=np.uint8,
    )


def test_read_parameters_returns_parsed_values(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    パラメータとファン数を正常に読み取れることを確認する。
    """
    engine.recognize_digits.side_effect = [
        "1234",
        "987",
        "1500",
        "123,456",
    ]

    cropped_by_class = {
        "vo_param": [dummy_image],
        "da_param": [dummy_image],
        "vi_param": [dummy_image],
        "fan_count": [dummy_image],
    }

    result = service.read_parameters(
        cropped_by_class,
        maximum=2300,
    )

    assert result == ParameterOcrResult(
        vo=1234,
        da=987,
        vi=1500,
        fans=123456,
    )

    assert engine.recognize_digits.call_count == 4


def test_read_parameters_returns_none_for_missing_images(
    service: OcrService,
    engine: Mock,
) -> None:
    """
    対象画像が存在しない項目はNoneになることを確認する。
    """
    result = service.read_parameters(
        {},
        maximum=2300,
    )

    assert result == ParameterOcrResult(
        vo=None,
        da=None,
        vi=None,
        fans=None,
    )

    engine.recognize_digits.assert_not_called()


def test_read_parameters_returns_none_for_invalid_values(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    最大値を超えたパラメータがNoneになることを確認する。
    """
    engine.recognize_digits.side_effect = [
        "9999",
        "1200",
        "1300",
        "50000",
    ]

    cropped_by_class = {
        "vo_param": [dummy_image],
        "da_param": [dummy_image],
        "vi_param": [dummy_image],
        "fan_count": [dummy_image],
    }

    result = service.read_parameters(
        cropped_by_class,
        maximum=2300,
    )

    assert result.vo is None
    assert result.da == 1200
    assert result.vi == 1300
    assert result.fans == 50000


def test_read_bonuses_returns_parsed_values(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    ボーナス値ときらめきを正常に読み取れることを確認する。
    """
    engine.recognize_percentage.side_effect = [
        "36.6%",
        "29%",
        "42.5%",
    ]
    engine.recognize_digits.return_value = "123"

    cropped_by_class = {
        "vo_bonus": [dummy_image],
        "da_bonus": [dummy_image],
        "vi_bonus": [dummy_image],
        "kirameki": [dummy_image],
    }

    result = service.read_bonuses(cropped_by_class)

    assert result == BonusOcrResult(
        vo=36.6,
        da=29.0,
        vi=42.5,
        kirameki=123,
    )

    assert engine.recognize_percentage.call_count == 3
    engine.recognize_digits.assert_called_once()


def test_read_bonuses_allows_missing_kirameki(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    きらめき画像がなくてもボーナス値を取得できることを確認する。
    """
    engine.recognize_percentage.side_effect = [
        "10%",
        "20%",
        "30%",
    ]

    cropped_by_class = {
        "vo_bonus": [dummy_image],
        "da_bonus": [dummy_image],
        "vi_bonus": [dummy_image],
    }

    result = service.read_bonuses(cropped_by_class)

    assert result == BonusOcrResult(
        vo=10.0,
        da=20.0,
        vi=30.0,
        kirameki=None,
    )


def test_read_scores_returns_parsed_values(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    合計スコアと各属性スコアを正常に読み取れることを確認する。
    """
    engine.recognize_digits.side_effect = [
        "60,000",
        "10,000",
        "20,000",
        "30,000",
    ]

    cropped_by_class = {
        "exam_score": [dummy_image],
        "vo_score": [dummy_image],
        "da_score": [dummy_image],
        "vi_score": [dummy_image],
    }

    result = service.read_scores(cropped_by_class)

    assert result == ScoreOcrResult(
        sum_score=60000,
        vo=10000,
        da=20000,
        vi=30000,
    )

    assert result.calculated_sum == 60000
    assert result.is_sum_consistent


def test_read_scores_detects_inconsistent_sum(
    service: OcrService,
    engine: Mock,
    dummy_image: np.ndarray,
) -> None:
    """
    表示合計と属性スコア合計が異なる場合を確認する。
    """
    engine.recognize_digits.side_effect = [
        "60,001",
        "10,000",
        "20,000",
        "30,000",
    ]

    cropped_by_class = {
        "exam_score": [dummy_image],
        "vo_score": [dummy_image],
        "da_score": [dummy_image],
        "vi_score": [dummy_image],
    }

    result = service.read_scores(cropped_by_class)

    assert result.calculated_sum == 60000
    assert not result.is_sum_consistent


def test_read_parameters_rejects_non_mapping(
    service: OcrService,
) -> None:
    """
    cropped_by_classがMappingでない場合に例外となることを確認する。
    """
    with pytest.raises(TypeError):
        service.read_parameters(
            [],
            maximum=2300,
        )


@pytest.mark.parametrize(
    "maximum",
    [
        0,
        -1,
        -2300,
    ],
)
def test_read_parameters_rejects_invalid_maximum(
    service: OcrService,
    maximum: int,
) -> None:
    """
    0以下のmaximumを拒否することを確認する。
    """
    with pytest.raises(ValueError):
        service.read_parameters(
            {},
            maximum=maximum,
        )


def test_read_parameters_rejects_non_integer_maximum(
    service: OcrService,
) -> None:
    """
    maximumが整数でない場合に例外となることを確認する。
    """
    with pytest.raises(TypeError):
        service.read_parameters(
            {},
            maximum=2300.0,
        )