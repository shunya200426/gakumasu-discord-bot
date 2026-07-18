"""
InferenceServiceの統合テスト。

実際のYOLOモデル、TesseractEngine、OCR前処理を使用して、
画像からInferenceResultが生成されるまでの一連の処理を確認する。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import cv2
import pytest

from inference.yolo_detector import YoloDetector
from ocr.tesseract_engine import TesseractEngine
from services.inference_service import InferenceService
from services.ocr_service import OcrService


PROJECT_ROOT = Path(__file__).resolve().parents[2]

YOLO_MODEL_PATH = (
    PROJECT_ROOT
    / "model_files"
    / "yolo"
    / "ui_detector.onnx"
)

TESSDATA_PATH = Path(
    "/usr/share/tesseract-ocr/5/tessdata"
)

IMAGE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "images"
    / "inference"
)

EXPECTED_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "expected"
    / "inference"
)


TEST_CASES = (
    (
        "schedule_nia",
        IMAGE_ROOT / "schedule" / "schedule_nia.png",
        EXPECTED_ROOT / "schedule_nia.json",
        2600,
        None,
    ),
    (
        "schedule_hif",
        IMAGE_ROOT / "schedule" / "schedule_hif.png",
        EXPECTED_ROOT / "schedule_hif.json",
        2600,
        1080,
    ),
    (
        "party_normal",
        IMAGE_ROOT / "formation" / "party_normal.png",
        EXPECTED_ROOT / "party_normal.json",
        2600,
        None,
    ),
    (
        "party_kirameki",
        IMAGE_ROOT / "formation" / "party_kirameki.png",
        EXPECTED_ROOT / "party_kirameki.json",
        2600,
        None,
    ),
    (
        "exam",
        IMAGE_ROOT / "exam" / "exam.png",
        EXPECTED_ROOT / "exam.json",
        2600,
        None,
    ),
)


@pytest.fixture(scope="module")
def inference_service() -> Iterator[InferenceService]:
    """
    実モデルとTesseractを使用するInferenceServiceを生成する。
    """
    detector = YoloDetector(
        model_path=YOLO_MODEL_PATH,
        confidence_threshold=0.25,
        image_size=(640, 640),
        device="cpu",
    )

    engine = TesseractEngine(
        tessdata_path=TESSDATA_PATH,
    )

    ocr_service = OcrService(
        engine=engine,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
        crop_padding=0,
    )

    yield service

    engine.close()


@pytest.mark.parametrize(
    (
        "case_name",
        "image_path",
        "expected_path",
        "parameter_maximum",
        "star_maximum",
    ),
    TEST_CASES,
    ids=[
        case[0]
        for case in TEST_CASES
    ],
)
def test_inference_service_with_real_model(
    inference_service: InferenceService,
    case_name: str,
    image_path: Path,
    expected_path: Path,
    parameter_maximum: int,
    star_maximum: int | None,
) -> None:
    """
    実画像をYOLO・OCRへ通し、期待値と一致することを確認する。
    """
    assert image_path.is_file(), (
        f"Test image does not exist: {image_path}"
    )

    assert expected_path.is_file(), (
        f"Expected JSON does not exist: {expected_path}"
    )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_COLOR,
    )

    assert image is not None, (
        f"Failed to load test image: {image_path}"
    )

    with expected_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        expected = json.load(file)

    result = inference_service.infer(
        image,
        parameter_maximum=parameter_maximum,
        star_maximum=star_maximum,
    )

    assert result.parameters.vo == expected["parameters"]["vo"]
    assert result.parameters.da == expected["parameters"]["da"]
    assert result.parameters.vi == expected["parameters"]["vi"]
    assert result.parameters.fans == expected["parameters"]["fans"]
    assert result.parameters.star == expected["parameters"]["star"]

    assert result.bonuses.vo == expected["bonuses"]["vo"]
    assert result.bonuses.da == expected["bonuses"]["da"]
    assert result.bonuses.vi == expected["bonuses"]["vi"]
    assert result.bonuses.kirameki == expected["bonuses"]["kirameki"]

    assert result.scores.sum_score == expected["scores"]["sum_score"]
    assert result.scores.vo == expected["scores"]["vo"]
    assert result.scores.da == expected["scores"]["da"]
    assert result.scores.vi == expected["scores"]["vi"]

    detected_classes = {
        detection.class_name
        for detection in result.detections
    }

    required_classes = set(
        expected["required_detection_classes"]
    )

    assert required_classes <= detected_classes, (
        f"Missing detection classes in {case_name}: "
        f"required={required_classes}, "
        f"detected={detected_classes}"
    )

    assert result.image_width == image.shape[1]
    assert result.image_height == image.shape[0]

    assert result.preprocess_ms >= 0.0
    assert result.inference_ms >= 0.0
    assert result.postprocess_ms >= 0.0
    assert result.total_ms >= 0.0

    assert result.total_ms >= result.inference_ms