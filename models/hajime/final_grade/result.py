# models/hajime/final_grade/result.py

from dataclasses import dataclass
from .params import HajimeFinalGradeParams

@dataclass
class HajimeFinalGradeResult(HajimeFinalGradeParams):
    # 最終試験順位ボーナスのパラメータ上昇量
    exam_post_bonus: int
    
    # 最終ステータス
    final_vo_status: int
    final_da_status: int
    final_vi_status: int
    
    # 最終試験後のステータスの評価値点数
    status_eval_points: int
    
    # 中間試験の評価値点数
    mid_exam_eval_points: int
    
    # 最終試験スコアの評価値点数
    final_exam_eval_points: int
    
    # 最終試験順位ボーナス
    final_exam_rank_bonus_points: int
    
    # 最終スコア
    final_point: int

    # 最終評価
    final_grade: str