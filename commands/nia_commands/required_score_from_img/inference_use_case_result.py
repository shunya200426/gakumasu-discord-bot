from __future__ import annotations

from dataclasses import dataclass, field

from models.nia.required_score_from_img.result import (
    NiaRequiredScoreFromImgResult,
)


@dataclass(slots=True)
class InferenceUseCaseResult:
    """
    画像推論から必要スコア計算までの実行結果。
    """

    parameters: dict[str, int | None]
    bonuses: dict[str, int | float | None]

    required_score_result: (
        NiaRequiredScoreFromImgResult | None
    ) = None

    pairs: list = field(
        default_factory=list
    )

    failed_sections: list[str] = field(
        default_factory=list
    )

    error_reason: str | None = None

    schedule_inference_ms: float = 0.0
    party_inference_ms: float = 0.0

    calculation_ms: float = 0.0

    @property
    def success(self) -> bool:
        return (
            not self.failed_sections
            and self.error_reason is None
            and self.required_score_result is not None
        )
