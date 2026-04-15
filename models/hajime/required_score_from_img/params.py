# required_score_from_img/params.py

import discord
from dataclasses import dataclass
from typing import Optional

@dataclass
class HajimeRequiredScoreFromImgParams:
    # モード
    mode: str
    
    # 試験終了時アビ点数
    vo_ability: int
    da_ability: int
    vi_ability: int

    # 入力画像
    schedule_img: discord.Attachment
    score_img: discord.Attachment
    
    # 使用キャラクター
    character: str = None

    # アイドル強化月間
    is_boost_active: bool = False
    party_img: discord.Attachment = None    # 月間時に使うかも

    # 目標評価/スコア
    target_grade: Optional[str] = None   
    target_score: Optional[int] = None   

    # 画像ログの同意
    save_agree: bool = False