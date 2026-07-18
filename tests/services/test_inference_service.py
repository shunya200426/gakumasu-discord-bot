"""
InferenceServiceの単体テスト。

YOLOモデルやTesseractは実行せず、
テスト用のDetector・OcrServiceを使用して、
各処理の接続とInferenceResultの生成を確認する。
"""

from __future__ import annotations

import numpy as np
import pytest

from inference.result import (
    BonusOcrResult,
    DetectionResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from inference.yolo_detector import YoloDetector
from services.inference_service import InferenceService
from services.ocr_service import CroppedImages, OcrService


class StubYoloDetector(YoloDetector):
    """
    YOLOモデルを読み込まず、固定の検出結果を返すテスト用Detector。
    """

    def __init__(
        self,
        detections: tuple[DetectionResult, ...],
    ) -> None:
        self._detections = detections
        self.received_image: np.ndarray | None = None
        self.received_confidence_threshold: float | None = None

    def detect(
        self,
        image: np.ndarray,
        *,
        confidence_threshold: float | None = None,
    ) -> tuple[DetectionResult, ...]:
        self.received_image = image
        self.received_confidence_threshold = confidence_threshold

        return self._detections


class StubOcrService(OcrService):
    """
    Tesseractを実行せず、固定のOCR結果を返すテスト用Service。
    """

    def __init__(
        self,
        *,
        parameters: ParameterOcrResult,
        bonuses: BonusOcrResult,
        scores: ScoreOcrResult,
    ) -> None:
        self._parameters = parameters
        self._bonuses = bonuses
        self._scores = scores

        self.received_parameters_crops: CroppedImages | None = None
        self.received_bonuses_crops: CroppedImages | None = None
        self.received_scores_crops: CroppedImages | None = None

        self.received_parameter_maximum: int | None = None
        self.received_star_maximum: int | None = None

    def read_parameters(
        self,
        cropped_by_class: CroppedImages,
        *,
        maximum: int,
        star_maximum: int | None = None,
    ) -> ParameterOcrResult:
        self.received_parameters_crops = cropped_by_class
        self.received_parameter_maximum = maximum
        self.received_star_maximum = star_maximum

        return self._parameters

    def read_bonuses(
        self,
        cropped_by_class: CroppedImages,
    ) -> BonusOcrResult:
        self.received_bonuses_crops = cropped_by_class

        return self._bonuses

    def read_scores(
        self,
        cropped_by_class: CroppedImages,
    ) -> ScoreOcrResult:
        self.received_scores_crops = cropped_by_class

        return self._scores


@pytest.fixture
def image() -> np.ndarray:
    """
    高さ100、幅200のテスト用BGR画像を返す。
    """
    return np.zeros(
        (100, 200, 3),
        dtype=np.uint8,
    )


@pytest.fixture
def detections() -> tuple[DetectionResult, ...]:
    return (
        DetectionResult(
            class_name="vo_param",
            confidence=0.95,
            x1=10,
            y1=20,
            x2=60,
            y2=50,
        ),
        DetectionResult(
            class_name="fan_count",
            confidence=0.90,
            x1=80,
            y1=20,
            x2=150,
            y2=50,
        ),
    )


@pytest.fixture
def parameters() -> ParameterOcrResult:
    return ParameterOcrResult(
        vo=1500,
        da=1600,
        vi=1700,
        fans=100000,
        star=50,
    )


@pytest.fixture
def bonuses() -> BonusOcrResult:
    return BonusOcrResult(
        vo=20.0,
        da=25.0,
        vi=30.0,
        kirameki=10,
    )


@pytest.fixture
def scores() -> ScoreOcrResult:
    return ScoreOcrResult(
        sum_score=60000,
        vo=20000,
        da=20000,
        vi=20000,
    )


def test_infer_returns_inference_result(
    image: np.ndarray,
    detections: tuple[DetectionResult, ...],
    parameters: ParameterOcrResult,
    bonuses: BonusOcrResult,
    scores: ScoreOcrResult,
) -> None:
    detector = StubYoloDetector(
        detections=detections,
    )

    ocr_service = StubOcrService(
        parameters=parameters,
        bonuses=bonuses,
        scores=scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
        crop_padding=0,
    )

    result = service.infer(
        image,
        parameter_maximum=2300,
        star_maximum=100,
        confidence_threshold=0.4,
    )

    assert result.parameters == parameters
    assert result.bonuses == bonuses
    assert result.scores == scores
    assert result.detections == detections

    assert result.image_width == 200
    assert result.image_height == 100

    assert result.preprocess_ms >= 0.0
    assert result.inference_ms >= 0.0
    assert result.postprocess_ms >= 0.0
    assert result.total_ms >= 0.0


def test_infer_passes_arguments_to_dependencies(
    image: np.ndarray,
    detections: tuple[DetectionResult, ...],
    parameters: ParameterOcrResult,
    bonuses: BonusOcrResult,
    scores: ScoreOcrResult,
) -> None:
    detector = StubYoloDetector(
        detections=detections,
    )

    ocr_service = StubOcrService(
        parameters=parameters,
        bonuses=bonuses,
        scores=scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
    )

    service.infer(
        image,
        parameter_maximum=2300,
        star_maximum=100,
        confidence_threshold=0.4,
    )

    assert detector.received_image is image
    assert detector.received_confidence_threshold == 0.4

    assert ocr_service.received_parameter_maximum == 2300
    assert ocr_service.received_star_maximum == 100

    assert ocr_service.received_parameters_crops is not None
    assert ocr_service.received_bonuses_crops is not None
    assert ocr_service.received_scores_crops is not None

    assert "vo_param" in ocr_service.received_parameters_crops
    assert "fan_count" in ocr_service.received_parameters_crops


def test_infer_crops_detected_regions(
    image: np.ndarray,
    detections: tuple[DetectionResult, ...],
    parameters: ParameterOcrResult,
    bonuses: BonusOcrResult,
    scores: ScoreOcrResult,
) -> None:
    detector = StubYoloDetector(
        detections=detections,
    )

    ocr_service = StubOcrService(
        parameters=parameters,
        bonuses=bonuses,
        scores=scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
    )

    service.infer(
        image,
        parameter_maximum=2300,
    )

    cropped = ocr_service.received_parameters_crops

    assert cropped is not None

    assert cropped["vo_param"][0].shape == (30, 50, 3)
    assert cropped["fan_count"][0].shape == (30, 70, 3)


def test_infer_returns_empty_ocr_result_when_no_detections(
    image: np.ndarray,
) -> None:
    detector = StubYoloDetector(
        detections=(),
    )

    empty_parameters = ParameterOcrResult()
    empty_bonuses = BonusOcrResult()
    empty_scores = ScoreOcrResult()

    ocr_service = StubOcrService(
        parameters=empty_parameters,
        bonuses=empty_bonuses,
        scores=empty_scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
    )

    result = service.infer(
        image,
        parameter_maximum=2300,
    )

    assert result.detections == ()
    assert result.parameters == empty_parameters
    assert result.bonuses == empty_bonuses
    assert result.scores == empty_scores

    assert ocr_service.received_parameters_crops == {}
    assert ocr_service.received_bonuses_crops == {}
    assert ocr_service.received_scores_crops == {}


@pytest.mark.parametrize(
    ("invalid_image", "exception_type"),
    [
        (None, TypeError),
        (np.array([], dtype=np.uint8), ValueError),
        (np.zeros((100, 200), dtype=np.uint8), ValueError),
        (np.zeros((100, 200, 4), dtype=np.uint8), ValueError),
    ],
)
def test_infer_rejects_invalid_image(
    invalid_image: object,
    exception_type: type[Exception],
    parameters: ParameterOcrResult,
    bonuses: BonusOcrResult,
    scores: ScoreOcrResult,
) -> None:
    detector = StubYoloDetector(
        detections=(),
    )

    ocr_service = StubOcrService(
        parameters=parameters,
        bonuses=bonuses,
        scores=scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
    )

    with pytest.raises(exception_type):
        service.infer(
            invalid_image,  # type: ignore[arg-type]
            parameter_maximum=2300,
        )


@pytest.mark.parametrize(
    ("parameter_maximum", "exception_type"),
    [
        (0, ValueError),
        (-1, ValueError),
        (2300.0, TypeError),
        ("2300", TypeError),
    ],
)
def test_infer_rejects_invalid_parameter_maximum(
    image: np.ndarray,
    parameter_maximum: object,
    exception_type: type[Exception],
    parameters: ParameterOcrResult,
    bonuses: BonusOcrResult,
    scores: ScoreOcrResult,
) -> None:
    detector = StubYoloDetector(
        detections=(),
    )

    ocr_service = StubOcrService(
        parameters=parameters,
        bonuses=bonuses,
        scores=scores,
    )

    service = InferenceService(
        detector=detector,
        ocr_service=ocr_service,
    )

    with pytest.raises(exception_type):
        service.infer(
            image,
            parameter_maximum=parameter_maximum,  # type: ignore[arg-type]
        )