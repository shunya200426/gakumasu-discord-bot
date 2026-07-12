"""
YOLOモデルの読み込みと推論を担当するモジュール。

Ultralyticsの推論結果を、Bot内部で使用するDetectionResultへ変換する。
画像切り出し、OCR、DB保存などはこのモジュールでは行わない。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from ultralytics import YOLO

from inference.result import DetectionResult
from utils.logger import get_logger


logger = get_logger()


class YoloDetector:
    """
    YOLOモデルを保持し、画像からUI領域を検出するクラス。

    モデルはインスタンス生成時に一度だけ読み込み、
    以降の推論では同じモデルを再利用する。
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        confidence_threshold: float = 0.25,
        image_size: tuple[int, int] = (640, 640),
        device: str | None = None,
    ) -> None:
        """
        YOLOモデルを初期化する。

        Args:
            model_path:
                読み込むYOLOモデルのパス。
            confidence_threshold:
                検出結果として採用する最低信頼度。
            image_size:
                推論時の入力サイズ。
                Ultralyticsでは (height, width) の順で指定する。
            device:
                推論に使用するデバイス。
                例: "cpu", "cuda:0"
                Noneの場合はUltralytics側の選択に任せる。

        Raises:
            FileNotFoundError:
                モデルファイルが存在しない場合。
            ValueError:
                設定値が不正な場合。
        """
        self._model_path = self._resolve_model_path(model_path)
        self._confidence_threshold = self._validate_confidence_threshold(
            confidence_threshold
        )
        self._image_size = self._validate_image_size(image_size)
        self._device = device

        logger.info(
            "Loading YOLO model: path=%s confidence=%.3f image_size=%s device=%s",
            self._model_path,
            self._confidence_threshold,
            self._image_size,
            self._device or "auto",
        )

        self._model = YOLO(
            str(self._model_path),
            task="detect",
        )

        logger.info(
            "YOLO model loaded: name=%s format=%s",
            self.model_name,
            self.model_format,
        )

    @property
    def model_path(self) -> Path:
        """モデルファイルの絶対パスを返す。"""
        return self._model_path

    @property
    def model_name(self) -> str:
        """拡張子を含むモデルファイル名を返す。"""
        return self._model_path.name

    @property
    def model_format(self) -> str:
        """モデルファイルの形式を返す。"""
        return self._model_path.suffix.lstrip(".").lower()

    @property
    def confidence_threshold(self) -> float:
        """現在の信頼度閾値を返す。"""
        return self._confidence_threshold

    @property
    def image_size(self) -> tuple[int, int]:
        """現在の推論入力サイズを返す。"""
        return self._image_size

    @property
    def class_names(self) -> dict[int, str]:
        """
        モデルが保持しているクラスIDとクラス名の対応を返す。
        """
        names = self._model.names

        if isinstance(names, dict):
            return {
                int(class_id): str(class_name)
                for class_id, class_name in names.items()
            }

        return {
            class_id: str(class_name)
            for class_id, class_name in enumerate(names)
        }

    def detect(
        self,
        image: np.ndarray,
        *,
        confidence_threshold: float | None = None,
    ) -> tuple[DetectionResult, ...]:
        """
        OpenCV画像に対してYOLO推論を実行する。

        Args:
            image:
                OpenCVで扱うBGR形式の画像。
            confidence_threshold:
                この推論だけで使用する信頼度閾値。
                Noneの場合は初期化時の値を使用する。

        Returns:
            検出結果のタプル。
            検出対象が存在しない場合は空タプルを返す。

        Raises:
            TypeError:
                入力がnumpy.ndarrayでない場合。
            ValueError:
                入力画像が空、または画像形式として不正な場合。
        """
        self._validate_image(image)

        threshold = (
            self._confidence_threshold
            if confidence_threshold is None
            else self._validate_confidence_threshold(confidence_threshold)
        )

        predict_options: dict[str, Any] = {
            "source": image,
            "conf": threshold,
            "imgsz": self._image_size,
            "verbose": False,
        }

        if self._device is not None:
            predict_options["device"] = self._device

        logger.debug(
            "YOLO inference started: shape=%s confidence=%.3f image_size=%s",
            image.shape,
            threshold,
            self._image_size,
        )

        results = self._model.predict(**predict_options)

        if not results:
            logger.warning("YOLO returned no result objects")
            return ()

        detections = self._convert_result(results[0])

        logger.debug(
            "YOLO inference completed: detections=%d",
            len(detections),
        )

        return detections

    def _convert_result(
        self,
        result: Any,
    ) -> tuple[DetectionResult, ...]:
        """
        Ultralyticsの推論結果をDetectionResultへ変換する。
        """
        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            return ()

        names = result.names
        detections: list[DetectionResult] = []

        xyxy_list = boxes.xyxy.cpu().tolist()
        confidence_list = boxes.conf.cpu().tolist()
        class_id_list = boxes.cls.cpu().tolist()

        for xyxy, confidence, class_id_value in zip(
            xyxy_list,
            confidence_list,
            class_id_list,
        ):
            class_id = int(class_id_value)
            class_name = self._get_class_name(names, class_id)

            x1, y1, x2, y2 = (
                int(round(float(coordinate)))
                for coordinate in xyxy
            )

            detection = DetectionResult(
                class_name=class_name,
                confidence=float(confidence),
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )

            if not detection.is_valid:
                logger.warning(
                    "Invalid detection skipped: class=%s bbox=(%d, %d, %d, %d)",
                    class_name,
                    x1,
                    y1,
                    x2,
                    y2,
                )
                continue

            detections.append(detection)

        return tuple(detections)

    @staticmethod
    def _get_class_name(
        names: dict[int, str] | list[str],
        class_id: int,
    ) -> str:
        """
        クラスIDに対応するクラス名を取得する。
        """
        if isinstance(names, dict):
            return str(names.get(class_id, f"unknown_{class_id}"))

        if 0 <= class_id < len(names):
            return str(names[class_id])

        return f"unknown_{class_id}"

    @staticmethod
    def _resolve_model_path(
        model_path: str | Path,
    ) -> Path:
        """
        モデルパスを展開・絶対パス化し、存在を確認する。
        """
        path = Path(model_path).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"YOLO model file does not exist: {path}"
            )

        return path

    @staticmethod
    def _validate_confidence_threshold(
        confidence_threshold: float,
    ) -> float:
        """
        信頼度閾値を検証する。
        """
        threshold = float(confidence_threshold)

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0.0 and 1.0: "
                f"{threshold}"
            )

        return threshold

    @staticmethod
    def _validate_image_size(
        image_size: tuple[int, int],
    ) -> tuple[int, int]:
        """
        推論入力サイズを検証する。
        """
        if len(image_size) != 2:
            raise ValueError(
                "image_size must be a tuple of (height, width)"
            )

        height, width = image_size

        if height <= 0 or width <= 0:
            raise ValueError(
                "image_size values must be greater than 0: "
                f"{image_size}"
            )

        return int(height), int(width)

    @staticmethod
    def _validate_image(
        image: np.ndarray,
    ) -> None:
        """
        入力画像がYOLO推論可能な形式か検証する。
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