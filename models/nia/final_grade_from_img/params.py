from dataclasses import dataclass
import discord

@dataclass
class NiaFinalGradeFromImgParams:
    # 使用キャラクター
    character: str
    
    # モード
    mode: str

    # オーディション
    audition: str

    # スケジュール画面
    schedule_img: discord.Attachment

    # 編成画面
    party_img: discord.Attachment

    # スコア画面
    score_img: discord.Attachment

    # チャレンジPアイテムの倍率
    challenge_P_item: int

    # アイドル強化月間
    is_boost_active: bool
    
    # 画像ログ
    save_agree: bool