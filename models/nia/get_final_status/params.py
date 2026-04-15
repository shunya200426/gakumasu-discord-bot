# get_final_status/params.py

from dataclasses import dataclass

@dataclass
class NiaGetFinalStatusParams:
    character: str      # 使用キャラクター

    mode: str           # モード

    audition_dict: dict      # 選択オーディション

    vo_bonus: float     # Voのパラメータボーナス
    da_bonus: float     # Daのパラメータボーナス
    vi_bonus: float     # Viのパラメータボーナス

    challenge_P_item: int   # チャレンジPアイテムの倍率

    set_over_line: int      # オーバーラインの設定