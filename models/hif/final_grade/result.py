# models/hif/final_grade/result.py

from dataclasses import dataclass

from .params import HifCalcScoreParams


@dataclass
class HifCalcScoreResult(HifCalcScoreParams):
    round1_score_corrected: int
    
    final_vo_status: int
    final_da_status: int
    final_vi_status: int

    status_eval_points: int
    round1_eval_points: int
    round2_eval_points: int

    round2_star_gain: int
    final_star: int
    star_eval_points: int

    final_point: int
    final_grade: str