from __future__ import annotations

from dataclasses import dataclass, field

from inference.result import InferenceResult
from models.nia.final_grade_from_img.result import (
    NiaFinalGradeFromImgResult,
)


@dataclass(slots=True)
class InferenceUseCaseResult:
    """
    画像推論から最終評価計算までの実行結果。
    """

    parameters: dict[str, int | None]
    bonuses: dict[str, int | float | None]
    scores: dict[str, int | None]

    schedule_inference: InferenceResult
    party_inference: InferenceResult
    score_inference: InferenceResult

    final_grade_result: (
        NiaFinalGradeFromImgResult | None
    ) = None

    failed_sections: list[str] = field(
        default_factory=list
    )

    error_reason: str | None = None

    calculation_ms: float = 0.0

    @property
    def schedule_inference_ms(self) -> float:
        return self.schedule_inference.total_ms

    @property
    def party_inference_ms(self) -> float:
        return self.party_inference.total_ms

    @property
    def score_inference_ms(self) -> float:
        return self.score_inference.total_ms

    @property
    def success(self) -> bool:
        return (
            not self.failed_sections
            and self.error_reason is None
            and self.final_grade_result is not None
        )
