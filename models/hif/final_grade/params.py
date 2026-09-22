# models/hif/final_grade/params.py

from dataclasses import dataclass


@dataclass
class HifFinalGradeParams:
    # モード
    mode: str

    # パラメータ
    vo_status: int
    da_status: int
    vi_status: int

    # 試験終了時アビ点数
    vo_ability: int
    da_ability: int
    vi_ability: int

    # R1 / R2スコア
    round1_score: int
    round2_score: int

    # R2開始前スター性
    star_before_round2: int

    # アイドル強化月間
    is_boost_active: bool
    kirameki: int

    # キャラクター
    character: str | None