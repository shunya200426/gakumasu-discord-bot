from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from inference.result import InferenceResult
from models.hajime.final_grade.result import (
    HajimeFinalGradeResult,
)

MidExamScoreSource = Literal["image", "manual"]


@dataclass(slots=True)
class InferenceUseCaseResult:
    """
    画像推論から最終評価計算までの実行結果。
    """

    parameters: dict[str, int | None]
    bonuses: dict[str, int | float | None]
    mid_exam_scores: dict[str, int | None]
    final_exam_scores: dict[str, int | None]

    mid_exam_score: int | None
    mid_exam_score_source: MidExamScoreSource

    final_exam_score: int | None

    schedule_inference: InferenceResult
    party_inference: InferenceResult
    final_exam_inference: InferenceResult
    mid_exam_inference: InferenceResult | None = None

    final_grade_result: HajimeFinalGradeResult | None = None
    failed_sections: list[str] = field(default_factory=list)
    error_reason: str | None = None
    calculation_ms: float = 0.0

    @property
    def schedule_inference_ms(self) -> float:
        return self.schedule_inference.total_ms

    @property
    def party_inference_ms(self) -> float:
        return self.party_inference.total_ms

    @property
    def mid_exam_inference_ms(self) -> float | None:
        if self.mid_exam_inference is None:
            return None
        return self.mid_exam_inference.total_ms

    @property
    def final_exam_inference_ms(self) -> float:
        return self.final_exam_inference.total_ms

    @property
    def success(self) -> bool:
        return (
            not self.failed_sections
            and self.error_reason is None
            and self.final_grade_result is not None
        )
