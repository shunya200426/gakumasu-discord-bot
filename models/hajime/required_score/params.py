# models/hajime/required_score/params.py

from dataclasses import dataclass

@dataclass
class HajimeRequiredScoreParams:
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
    
    # 中間試験スコア
    mid_exam_score: int
    
    # 目標評価グレード
    target_grade: str
    target_score: int
    
    # キャラクター
    character: str
    
    # アイドル強化月間
    is_boost_active: bool
    kirameki: int