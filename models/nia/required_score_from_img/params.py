# required_score_from_img/params.py

import discord
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class NiaRequiredScoreFromImgParams:
    # 使用キャラクター
    character: str
    
    # モード
    mode: str

    # オーディション
    audition: str

    # 入力画像
    schedule_img: discord.Attachment
    party_img: discord.Attachment

    # チャレンジPアイテムの倍率
    challenge_P_item: int

    # アイドル強化月間
    is_boost_active: bool

    # 目標評価/スコア
    target_grade: Optional[str] = None   
    target_score: Optional[int] = None   

    # 画像ログの同意
    save_agree: bool = False