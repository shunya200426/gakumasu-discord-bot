"""
画像に対するYOLO推論・切り出し・OCR処理を統括するサービス。

このモジュールでは、入力画像に対して以下の処理を順番に実行する。

1. YOLOによる領域検出
2. 検出領域の切り出し
3. OCRによる数値読み取り
4. InferenceResultへの集約

Discordコマンドへの応答生成やDB保存は担当しない。
"""

from __future__ import annotations

from time import perf_counter

import numpy as np

from inference.cropper import crop_detections
from inference.result import InferenceResult
from inference.yolo_detector import YoloDetector
from services.ocr_service import OcrService
from utils.logger import get_logger


logger = get_logger()


class InferenceService:
    """
    YOLO推論からOCR結果生成までを統括するサービス。

    YoloDetectorとOcrServiceは外部から受け取り、
    Bot起動中は同じインスタンスを再利用する。
    """

    def __init__(
        self,
        detector: YoloDetector,
        ocr_service: OcrService,
        *,
        crop_padding: int = 0,
    ) -> None:
        """
        InferenceServiceを初期化する。

        Args:
            detector:
                UI領域の検出に使用するYoloDetector。
            ocr_service:
                切り出し画像のOCRに使用するOcrService。
            crop_padding:
                YOLOのBounding Boxへ追加する余白。
        """
        if not isinstance(detector, YoloDetector):
            raise TypeError(
                "detector must be YoloDetector: "
                f"{type(detector).__name__}"
            )

        if not isinstance(ocr_service, OcrService):
            raise TypeError(
                "ocr_service must be OcrService: "
                f"{type(ocr_service).__name__}"
            )

        self._validate_crop_padding(crop_padding)

        self._detector = detector
        self._ocr_service = ocr_service
        self._crop_padding = crop_padding

    @property
    def detector(self) -> YoloDetector:
        """使用中のYoloDetectorを返す。"""
        return self._detector

    @property
    def ocr_service(self) -> OcrService:
        """使用中のOcrServiceを返す。"""
        return self._ocr_service

    @property
    def crop_padding(self) -> int:
        """切り出し時に使用する余白を返す。"""
        return self._crop_padding

    def infer(
        self,
        image: np.ndarray,
        *,
        parameter_maximum: int,
        star_maximum: int | None = None,
        confidence_threshold: float | None = None,
    ) -> InferenceResult:
        """
        画像に対してYOLO推論・切り出し・OCR処理を実行する。

        Args:
            image:
                OpenCVで扱うBGR形式の画像。
            parameter_maximum:
                Vo・Da・Viパラメータの最大値。
            star_maximum:
                スター性の最大値。
                Noneの場合は上限を設定しない。
            confidence_threshold:
                この推論だけで使用するYOLOの信頼度閾値。
                Noneの場合はYoloDetectorの設定値を使用する。

        Returns:
            YOLO検出結果、OCR結果、画像サイズ、
            各処理時間をまとめたInferenceResult。

        Raises:
            TypeError:
                入力画像や引数の型が不正な場合。
            ValueError:
                入力画像や設定値が不正な場合。
        """
        total_started_at = perf_counter()

        preprocess_started_at = perf_counter()

        self._validate_image(image)
        self._validate_maximum(
            parameter_maximum,
            argument_name="parameter_maximum",
        )

        if star_maximum is not None:
            self._validate_maximum(
                star_maximum,
                argument_name="star_maximum",
            )

        image_height, image_width = image.shape[:2]

        preprocess_ms = self._elapsed_ms(
            preprocess_started_at,
        )

        logger.debug(
            "Inference started: "
            "image_size=(%d, %d) "
            "parameter_maximum=%d "
            "star_maximum=%s "
            "confidence_threshold=%s",
            image_width,
            image_height,
            parameter_maximum,
            star_maximum,
            confidence_threshold,
        )

        inference_started_at = perf_counter()

        detections = self._detector.detect(
            image,
            confidence_threshold=confidence_threshold,
        )

        inference_ms = self._elapsed_ms(
            inference_started_at,
        )

        postprocess_started_at = perf_counter()

        cropped_by_class = crop_detections(
            image=image,
            detections=detections,
            padding=self._crop_padding,
            copy=True,
        )

        parameters = self._ocr_service.read_parameters(
            cropped_by_class,
            maximum=parameter_maximum,
            star_maximum=star_maximum,
        )

        bonuses = self._ocr_service.read_bonuses(
            cropped_by_class,
        )

        scores = self._ocr_service.read_scores(
            cropped_by_class,
        )

        postprocess_ms = self._elapsed_ms(
            postprocess_started_at,
        )

        total_ms = self._elapsed_ms(
            total_started_at,
        )

        result = InferenceResult(
            parameters=parameters,
            bonuses=bonuses,
            scores=scores,
            detections=detections,
            image_width=image_width,
            image_height=image_height,
            preprocess_ms=preprocess_ms,
            inference_ms=inference_ms,
            postprocess_ms=postprocess_ms,
            total_ms=total_ms,
        )

        logger.debug(
            "Inference completed: "
            "detections=%d "
            "preprocess_ms=%.3f "
            "inference_ms=%.3f "
            "postprocess_ms=%.3f "
            "total_ms=%.3f",
            len(result.detections),
            result.preprocess_ms,
            result.inference_ms,
            result.postprocess_ms,
            result.total_ms,
        )

        return result

    @staticmethod
    def _elapsed_ms(
        started_at: float,
    ) -> float:
        """
        指定した開始時刻からの経過時間をミリ秒で返す。
        """
        return (perf_counter() - started_at) * 1000.0

    @staticmethod
    def _validate_image(
        image: np.ndarray,
    ) -> None:
        """
        入力画像が推論可能なBGR画像か検証する。
        """
        if not isinstance(image, np.ndarray):
            raise TypeError(
                "image must be numpy.ndarray: "
                f"{type(image).__name__}"
            )

        if image.size == 0:
            raise ValueError("image is empty")

        if image.ndim != 3:
            raise ValueError(
                "image must be a 3-dimensional BGR image: "
                f"shape={image.shape}"
            )

        if image.shape[2] != 3:
            raise ValueError(
                "image must have 3 color channels: "
                f"shape={image.shape}"
            )

    @staticmethod
    def _validate_maximum(
        maximum: int,
        *,
        argument_name: str,
    ) -> None:
        """
        OCRに使用する最大値を検証する。
        """
        if not isinstance(maximum, int):
            raise TypeError(
                f"{argument_name} must be int: "
                f"{type(maximum).__name__}"
            )

        if maximum <= 0:
            raise ValueError(
                f"{argument_name} must be greater than 0: "
                f"{maximum}"
            )

    @staticmethod
    def _validate_crop_padding(
        crop_padding: int,
    ) -> None:
        """
        切り出し時の余白を検証する。
        """
        if not isinstance(crop_padding, int):
            raise TypeError(
                "crop_padding must be int: "
                f"{type(crop_padding).__name__}"
            )

        if crop_padding < 0:
            raise ValueError(
                "crop_padding must be 0 or greater: "
                f"{crop_padding}"
            )