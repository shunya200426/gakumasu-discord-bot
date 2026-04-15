# get_final_status/result.py

from dataclasses import dataclass
from .params import NiaGetFinalStatusParams

@dataclass
class NiaGetFinalStatusResult(NiaGetFinalStatusParams):
    max_status: int     # 設定されたパラメータの上限