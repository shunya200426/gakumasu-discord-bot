# models/param_spec.py
from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence, Callable

Kind = Literal["int","float","bool","choice","text"]

@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    kind: Kind
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[Sequence[tuple[str, Any]]] = None  # [(表示名, 値)]
    required: bool = True
    visible_when: Optional[Callable[[dict], bool]] = None  # 依存表示（例：強化月間ONのときだけ表示）
    help: Optional[str] = None
