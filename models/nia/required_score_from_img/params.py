# required_score_from_img/params.py

from dataclasses import dataclass

import discord


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
    target_grade: str | None = None   
    target_score: int | None = None   

    # 今回指定された画像保存同意
    image_save_consent: bool | None = None
