from __future__ import annotations

from dataclasses import dataclass, field

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

    final_grade_result: (
        NiaFinalGradeFromImgResult | None
    ) = None

    failed_sections: list[str] = field(
        default_factory=list
    )

    error_reason: str | None = None

    schedule_inference_ms: float = 0.0
    party_inference_ms: float = 0.0
    score_inference_ms: float = 0.0

    calculation_ms: float = 0.0

    @property
    def success(self) -> bool:
        return (
            not self.failed_sections
            and self.error_reason is None
            and self.final_grade_result is not None
        )