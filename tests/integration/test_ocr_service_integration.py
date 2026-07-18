from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from ocr.tesseract_engine import TesseractEngine
from services.ocr_service import OcrService


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
IMAGE_ROOT = FIXTURES_ROOT / "images" / "ocr"
EXPECTED_ROOT = FIXTURES_ROOT / "expected"


def load_expected(filename: str) -> dict[str, dict[str, int | float]]:
    """
    期待値JSONを読み込む。
    """
    path = EXPECTED_ROOT / filename

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_image(
    class_name: str,
    filename: str,
):
    """
    OCRテスト用画像をOpenCVで読み込む。
    """
    path = IMAGE_ROOT / class_name / filename

    image = cv2.imread(str(path))

    if image is None:
        raise FileNotFoundError(
            f"Failed to load test image: {path}"
        )

    return image


@pytest.fixture(scope="module")
def ocr_service():
    """
    実Tesseractを使用するOcrServiceを作成する。
    """
    engine = TesseractEngine(
        tessdata_path="/usr/share/tesseract-ocr/5/tessdata",
    )
    service = OcrService(engine)

    yield service

    engine.close()


@pytest.mark.parametrize(
    ("class_name", "filename", "expected"),
    [
        (
            class_name,
            filename,
            expected,
        )
        for class_name, cases in load_expected(
            "parameters.json"
        ).items()
        for filename, expected in cases.items()
    ],
)
def test_parameter_ocr(
    ocr_service: OcrService,
    class_name: str,
    filename: str,
    expected: int,
) -> None:
    """
    パラメータ系OCRを実画像で検証する。
    """
    image = load_image(
        class_name,
        filename,
    )

    cropped_by_class = {
        class_name: [image],
    }

    result = ocr_service.read_parameters(
        cropped_by_class,
        maximum=2300,
    )

    actual = {
        "vo_param": result.vo,
        "da_param": result.da,
        "vi_param": result.vi,
        "fan_count": result.fans,
        "star_param": result.star,
    }[class_name]

    assert actual == expected


@pytest.mark.parametrize(
    ("class_name", "filename", "expected"),
    [
        (
            class_name,
            filename,
            expected,
        )
        for class_name, cases in load_expected(
            "bonuses.json"
        ).items()
        for filename, expected in cases.items()
    ],
)
def test_bonus_ocr(
    ocr_service: OcrService,
    class_name: str,
    filename: str,
    expected: int | float,
) -> None:
    """
    ボーナス系OCRを実画像で検証する。
    """
    image = load_image(
        class_name,
        filename,
    )

    cropped_by_class = {
        class_name: [image],
    }

    result = ocr_service.read_bonuses(
        cropped_by_class,
    )

    actual = {
        "vo_bonus": result.vo,
        "da_bonus": result.da,
        "vi_bonus": result.vi,
        "kirameki": result.kirameki,
    }[class_name]

    assert actual == expected


@pytest.mark.parametrize(
    ("class_name", "filename", "expected"),
    [
        (
            class_name,
            filename,
            expected,
        )
        for class_name, cases in load_expected(
            "scores.json"
        ).items()
        for filename, expected in cases.items()
    ],
)
def test_score_ocr(
    ocr_service: OcrService,
    class_name: str,
    filename: str,
    expected: int,
) -> None:
    """
    スコア系OCRを実画像で検証する。
    """
    image = load_image(
        class_name,
        filename,
    )

    cropped_by_class = {
        class_name: [image],
    }

    result = ocr_service.read_scores(
        cropped_by_class,
    )

    actual = {
        "exam_score": result.sum_score,
        "vo_score": result.vo,
        "da_score": result.da,
        "vi_score": result.vi,
    }[class_name]

    assert actual == expected