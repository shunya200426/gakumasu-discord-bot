# required_score_from_img/params.py

from dataclasses import dataclass

import discord


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
    party_img: discord.Attachment

    # 中間試験のスコア
    mid_exam_score: int
    mid_exam_score_img: discord.Attachment = None

    # 使用キャラクター
    character: str = None

    # アイドル強化月間
    is_boost_active: bool = False

    # 目標評価/スコア
    target_grade: str | None = None   
    target_score: int | None = None   

    # 画像ログの同意
    save_agree: bool = False