from dataclasses import dataclass

import discord


@dataclass
class HajimeFinalGradeFromImgParams:
    mode: str
    vo_ability: int
    da_ability: int
    vi_ability: int
    schedule_img: discord.Attachment
    party_img: discord.Attachment
    final_exam_score_img: discord.Attachment
    mid_exam_score: int
    final_exam_rank: str
    mid_exam_score_img: discord.Attachment | None = None
    character: str | None = None
    is_boost_active: bool = False
    save_agree: bool | None = None
