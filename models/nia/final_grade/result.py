# models/nia/final_grade_result.py
from dataclasses import dataclass
from .params import NiaFinalGradeParams

@dataclass
class NiaFinalGradeResult(NiaFinalGradeParams):
    # 最終スコア
    final_score: int

    # 最終評価
    final_grade: str

    # それぞれのスコアの内訳
    status_score: int
    fan_score: int

    # ステータス上昇量
    get_vo_status: int
    get_da_status: int
    get_vi_status: int

    # 最終ステータス
    final_vo_status: int
    final_da_status: int
    final_vi_status: int

    # ファン数/ファングレード
    get_fans: int
    final_fans: int
    fan_grade: str