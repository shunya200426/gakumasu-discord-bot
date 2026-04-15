# models/hajime/final_grade/params.py

from dataclasses import dataclass

@dataclass
class HajimeFinalGradeParams:
    # モード
    mode: str

    # それぞれの試験前パラメータ
    vo_status: int
    da_status: int
    vi_status: int
    
    # 試験終了時アビ点数
    vo_ability: int
    da_ability: int
    vi_ability: int

    # 中間試験のスコア
    mid_exam_score: int
    
    # 最終試験スコア
    final_exam_score: int
    
    # 試験順位
    final_exam_rank: int
    
    # キャラクター
    character: str
    
    # アイドル強化月間
    is_boost_active: bool
    kirameki: int