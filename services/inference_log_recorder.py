"""
推論結果のDB記録を統括するサービス。

InferenceResultを受け取り、推論ログと検出結果を
1つのトランザクションとして保存する。
"""

from __future__ import annotations

from typing import Literal

from db.repositories.inference_repository import (
    InferenceRepository,
)
from inference.result import InferenceResult
from inference.yolo_detector import YoloDetector

ImageRole = Literal[
    "schedule",
    "party",
    "score",
]

InferenceStatus = Literal[
    "SUCCESS",
    "OCR_FAILED",
    "ERROR",
]


class InferenceLogRecorder:
    """
    推論ログと検出結果の保存を統括する。

    SQLの実行自体はInferenceRepositoryへ委譲し、
    このクラスでは親となる推論ログと、
    子となる検出結果の一括保存を担当する。
    """

    def __init__(
        self,
        repository: InferenceRepository,
        detector: YoloDetector,
    ) -> None:
        self._repository = repository
        self._detector = detector

    def save(
        self,
        *,
        request_id: str,
        guild_id: int | None,
        channel_id: int | None,
        user_id: int | None,
        command_name: str,
        image_role: ImageRole,
        image_path: str | None,
        export_path: str | None,
        inference_result: InferenceResult,
        status: InferenceStatus,
    ) -> int:
        """
        推論ログと検出結果をまとめて保存する。

        保存処理全体を1つのトランザクションとして扱い、
        途中で例外が発生した場合はすべてrollbackする。

        Returns:
            作成されたinference_logs.id。

        Raises:
            sqlite3.Error:
                DBへの保存に失敗した場合。
        """
        connection = self._repository.connection

        with connection:
            inference_log_id = (
                self._repository.save_inference_log(
                    request_id=request_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    image_role=image_role,
                    image_path=image_path,
                    export_path=export_path,
                    model_name=self._detector.model_name,
                    model_format=self._detector.model_format,
                    image_width=(
                        inference_result.image_width
                    ),
                    image_height=(
                        inference_result.image_height
                    ),
                    preprocess_ms=(
                        inference_result.preprocess_ms
                    ),
                    inference_ms=(
                        inference_result.inference_ms
                    ),
                    postprocess_ms=(
                        inference_result.postprocess_ms
                    ),
                    total_ms=(
                        inference_result.total_ms
                    ),
                    status=status,
                )
            )

            for detection in (
                inference_result.detections
            ):
                self._repository.save_detection_result(
                    inference_log_id=(
                        inference_log_id
                    ),
                    class_name=(
                        detection.class_name
                    ),
                    confidence=(
                        detection.confidence
                    ),
                    x1=detection.x1,
                    y1=detection.y1,
                    x2=detection.x2,
                    y2=detection.y2,
                    crop_path=None,
                )

        return inference_log_id