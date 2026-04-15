from typing import Any
from .settings import SETTINGS

# ---- 共通 ----
def get_characters() -> dict[str, Any]:
    return SETTINGS["characters"]

def get_character(ch_key: str) -> dict[str, Any]:
    return SETTINGS["characters"][ch_key]

def get_character_trend(ch_key: str) -> dict[str, Any]:
    return SETTINGS["characters"][ch_key]["trend"]

def get_stat_multiplier() -> float:
    return SETTINGS["stat_multiplier"]

def get_grade_thresholds() -> dict[str, int]:
    return SETTINGS["grade_thresholds"]

def get_boost_config() -> dict[str, Any]:
    return SETTINGS["boost"]

# ---- Hajime ----
def get_hajime() -> dict[str, Any]:
    return SETTINGS["Hajime"]

def get_hajime_mode_cap(mode: str) -> int:
    return SETTINGS["Hajime"][mode]["st_max"]

def get_hajime_score_attenuation() -> dict[str, Any]:
    return SETTINGS["Hajime"]["score_attenuation"]

def get_hajime_reverse_score_attenuation() -> dict[str, Any]:
    return SETTINGS["Hajime"]["reverse_score_attenuation"]

# ---- NIA ----
def get_nia() -> dict[str, Any]:
    return SETTINGS["NIA"]

def get_nia_mode_cap(mode: str) -> int:
    return SETTINGS["NIA"][mode]["st_max"]

def get_nia_fan_grade() -> dict[str, Any]:
    return SETTINGS["NIA"]["fan_grade"]

def get_nia_audition_fan_block(mode: str, audition: str) -> dict[str, Any]:
    return SETTINGS["NIA"][mode][audition]["fan"]

def get_nia_audition_status_block(mode: str, audition: str, trend_type: str) -> dict[str, Any]:
    return SETTINGS["NIA"][mode][audition]["status"][trend_type]
