# models/hajime/required_score/result.py

from dataclasses import dataclass

from .params import HajimeRequiredScoreParams


@dataclass
class HajimeRequiredScoreResult(HajimeRequiredScoreParams):
    # SSからSSS+までの要求スコアを取得
    SS_required_score: int | str | None = None
    SS_plus_required_score: int | str | None = None
    SSS_required_score: int | str | None = None
    SSS_plus_required_score: int | str | None = None

    Target_grade_required_score: int | str | None = None
    Target_score_required_score: int | str | None = None
