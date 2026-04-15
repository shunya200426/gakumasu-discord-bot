# required_score/params.py

from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class NiaRequiredScoreParams:
    # 使用キャラクター
    character: str
    
    # モード
    mode: str

    # オーディション
    audition: str

    # 現在のそれぞれのステータス値
    vo_status: int
    da_status: int
    vi_status: int

    # レッスンボーナス
    vo_bonus: float
    da_bonus: float
    vi_bonus: float

    # 現在のファン数
    now_fans: int

    # チャレンジPアイテムの倍率
    challenge_P_item: int

    # アイドル強化月間
    is_boost_active: bool
    kirameki: int

    # 目標評価/スコア
    target_grade: Optional[str] = None   
    target_score: Optional[int] = None   