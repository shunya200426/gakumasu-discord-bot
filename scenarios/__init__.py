# 公開するシナリオクラスのみをimport
from .hajime_scenario import HajimeScenario
from .nia_scenario import NiaScenario

# __all__で外部公開するシンボルを制御
__all__ = [
    "HajimeScenario",
    "NiaScenario",
]
