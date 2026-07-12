"""
OCRで取得した文字列を、Bot内部で扱える値へ変換するモジュール。

このモジュールではOCR自体は実行せず、
文字列の正規化・補正・数値変換のみを担当する。
"""

from __future__ import annotations

import re


def normalize_ocr_text(text: str) -> str:
    """
    OCR文字列の表記揺れを正規化する。

    主な変換:
        - 全角パーセントを半角へ変換
        - 全角ピリオドや類似記号を半角ピリオドへ変換
        - 全角カンマを半角カンマへ変換
        - 空白や改行を除去

    Args:
        text:
            OCRで取得した生文字列。

    Returns:
        正規化済み文字列。
    """
    if not isinstance(text, str):
        raise TypeError(
            "text must be str: "
            f"{type(text).__name__}"
        )

    return (
        text.strip()
        .replace("％", "%")
        .replace("．", ".")
        .replace("，", ",")
        .replace("·", ".")
        .replace("•", ".")
        .replace("。", ".")
        .replace("\n", "")
        .replace("\r", "")
        .replace("\t", "")
        .replace(" ", "")
    )


def parse_integer(
    text: str,
    *,
    allow_comma: bool = True,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    """
    OCR文字列から整数を取得する。

    Args:
        text:
            OCRで取得した文字列。
        allow_comma:
            Trueの場合、桁区切りカンマを除去する。
        minimum:
            許容する最小値。
        maximum:
            許容する最大値。

    Returns:
        変換できた整数。
        数字が存在しない、または範囲外の場合はNone。
    """
    normalized = normalize_ocr_text(text)

    if allow_comma:
        normalized = normalized.replace(",", "")

    digits = "".join(
        character
        for character in normalized
        if character.isdigit()
    )

    if not digits:
        return None

    value = int(digits)

    if minimum is not None and value < minimum:
        return None

    if maximum is not None and value > maximum:
        return None

    return value


def parse_percentage(
    text: str,
    *,
    require_percent_sign: bool = False,
    return_ratio: bool = False,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    """
    OCR文字列からパーセント値を取得する。

    Args:
        text:
            OCRで取得した文字列。
        require_percent_sign:
            Trueの場合、%記号が存在しなければNoneを返す。
        return_ratio:
            Trueの場合、36.6%を0.366として返す。
            Falseの場合、36.6として返す。
        minimum:
            許容する最小値。
        maximum:
            許容する最大値。

    Returns:
        変換できたfloat値。
        変換失敗または範囲外の場合はNone。

    Examples:
        "36.6%" -> 36.6
        "29%"   -> 29.0
        "36,6%" -> 36.6
    """
    normalized = normalize_ocr_text(text)

    has_percent_sign = "%" in normalized

    if require_percent_sign and not has_percent_sign:
        return None

    # 小数点として誤認識されたカンマを補正
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")

    match = re.search(
        r"(\d+(?:\.\d+)?)%?",
        normalized,
    )

    if match is None:
        return None

    value = float(match.group(1))

    if minimum is not None and value < minimum:
        return None

    if maximum is not None and value > maximum:
        return None

    if return_ratio:
        value /= 100.0

    return value


def split_three_parameters(
    text: str,
    *,
    minimum: int = 0,
    maximum: int,
    fallback_minimum: int | None = 200,
) -> tuple[int, int, int]:
    """
    連結された数字列をVo・Da・Viの3値へ分割する。

    各値は3桁または4桁とし、4桁を多く含む分割を優先する。

    Args:
        text:
            OCRで取得した連続数字列。
        minimum:
            各値の下限。
        maximum:
            各値の上限。
        fallback_minimum:
            通常の下限で失敗した場合に使用する緩和下限。
            Noneの場合はフォールバックしない。

    Returns:
        `(vo, da, vi)` のタプル。

    Raises:
        ValueError:
            3値へ分割できない場合。
    """
    normalized = normalize_ocr_text(text)

    digits = "".join(
        character
        for character in normalized
        if character.isdigit()
    )

    if not digits:
        raise ValueError(
            f"No digits found: text={text!r}"
        )

    result = _try_split_three_parameters(
        digits,
        minimum=minimum,
        maximum=maximum,
    )

    if result is not None:
        return result

    if (
        fallback_minimum is not None
        and fallback_minimum < minimum
    ):
        result = _try_split_three_parameters(
            digits,
            minimum=fallback_minimum,
            maximum=maximum,
        )

        if result is not None:
            return result

    raise ValueError(
        "Failed to split three parameters: "
        f"digits={digits!r}, length={len(digits)}, "
        f"minimum={minimum}, maximum={maximum}"
    )


def _try_split_three_parameters(
    digits: str,
    *,
    minimum: int,
    maximum: int,
) -> tuple[int, int, int] | None:
    """
    指定された範囲で3値への分割を試行する。
    """
    digit_count = len(digits)

    patterns: list[tuple[int, int, int]] = []

    for first_length in (3, 4):
        for second_length in (3, 4):
            for third_length in (3, 4):
                pattern = (
                    first_length,
                    second_length,
                    third_length,
                )

                if sum(pattern) == digit_count:
                    patterns.append(pattern)

    # 4桁の値を多く含むパターンを優先
    patterns.sort(
        key=lambda pattern: -sum(
            length == 4
            for length in pattern
        )
    )

    for first_length, second_length, third_length in patterns:
        first = digits[:first_length]
        second = digits[
            first_length:
            first_length + second_length
        ]
        third = digits[
            first_length + second_length:
            first_length + second_length + third_length
        ]

        segments = (first, second, third)

        if all(
            _is_valid_parameter_segment(
                segment,
                minimum=minimum,
                maximum=maximum,
            )
            for segment in segments
        ):
            return (
                int(first),
                int(second),
                int(third),
            )

    return None


def _is_valid_parameter_segment(
    segment: str,
    *,
    minimum: int,
    maximum: int,
) -> bool:
    """
    パラメータ候補文字列が有効か判定する。
    """
    if not segment:
        return False

    if segment.startswith("0"):
        return False

    value = int(segment)

    return minimum < value <= maximum