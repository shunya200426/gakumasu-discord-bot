# models/hajime/required_score/result.py

from dataclasses import dataclass
from typing import Optional
from .params import HajimeRequiredScoreParams

@dataclass
class HajimeRequiredScoreResult(HajimeRequiredScoreParams):
    # SSからSSS+までの要求スコアを取得
    SS_required_score: Optional[int] = None
    SS_plus_required_score: Optional[int] = None
    SSS_required_score: Optional[int] = None
    SSS_plus_required_score: Optional[int] = None

    Target_grade_required_score: Optional[int] = None
    Target_score_required_score: Optional[int] = None