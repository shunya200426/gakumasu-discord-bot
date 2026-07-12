"""
OCR前に適用する画像処理を定義するモジュール。

このモジュールでは画像のグレースケール化、拡大、
二値化などを行う。OCR実行や文字列の解析は行わない。
"""

from __future__ import annotations

import cv2
import numpy as np


DEFAULT_SCALE = 3.0


def preprocess_digits(
    image: np.ndarray,
    *,
    scale: float = DEFAULT_SCALE,
) -> np.ndarray:
    """
    整数OCR向けの前処理を行う。

    Notebookで動作確認済みの以下の処理を適用する。

    1. グレースケール化
    2. INTER_CUBICによる拡大
    3. 大津の二値化
    4. 白背景・黒文字へ整形

    Args:
        image:
            OpenCV形式の入力画像。
            BGR画像またはグレースケール画像を受け付ける。
        scale:
            拡大倍率。既定値は3.0。

    Returns:
        前処理済みの1チャンネル二値画像。

    Raises:
        TypeError:
            imageがnumpy.ndarrayでない場合。
        ValueError:
            空画像、未対応の画像形式、不正な拡大率の場合。
    """
    _validate_image(image)
    _validate_scale(scale)

    gray = to_grayscale(image)

    resized = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )

    _, binary = cv2.threshold(
        resized,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    return binary


def preprocess_percentage(
    image: np.ndarray,
    *,
    scale: float = DEFAULT_SCALE,
    left_trim_ratio: float = 0.25,
) -> np.ndarray:
    """
    小数・パーセントOCR向けの前処理を行う。

    左側に含まれる属性アイコンを除去した後、
    拡大と大津の二値化を適用する。

    Args:
        image:
            OpenCV形式の入力画像。
        scale:
            拡大倍率。
        left_trim_ratio:
            画像左側から除去する幅の割合。
    """
    _validate_image(image)
    _validate_scale(scale)

    if not isinstance(left_trim_ratio, int | float):
        raise TypeError(
            "left_trim_ratio must be int or float: "
            f"{type(left_trim_ratio).__name__}"
        )

    if not 0.0 <= left_trim_ratio < 1.0:
        raise ValueError(
            "left_trim_ratio must be between 0.0 and 1.0: "
            f"{left_trim_ratio}"
        )

    width = image.shape[1]
    trim_x = int(round(width * left_trim_ratio))

    trimmed = image[:, trim_x:]

    if trimmed.size == 0:
        raise ValueError(
            "percentage image became empty after trimming: "
            f"width={width}, left_trim_ratio={left_trim_ratio}"
        )

    return preprocess_digits(
        trimmed,
        scale=scale,
    )


def preprocess_parameter(
    image: np.ndarray,
) -> np.ndarray:
    """
    Vo・Da・Viパラメータ向けの前処理を行う。

    YOLO切り出し画像は十分に鮮明なため、
    グレースケール化のみ適用する。
    """
    return to_grayscale(image)


def preprocess_fans(
    image: np.ndarray,
    *,
    scale: float = DEFAULT_SCALE,
) -> np.ndarray:
    """
    ファン数向けの前処理を行う。
    """
    return preprocess_digits(
        image,
        scale=scale,
    )


def preprocess_score(
    image: np.ndarray,
    *,
    scale: float = DEFAULT_SCALE,
) -> np.ndarray:
    """
    オーディションスコア向けの前処理を行う。
    """
    return preprocess_digits(
        image,
        scale=scale,
    )


def preprocess_kirameki(
    image: np.ndarray,
    *,
    scale: float = DEFAULT_SCALE,
) -> np.ndarray:
    """
    ほしのきらめき向けの前処理を行う。
    """
    return preprocess_digits(
        image,
        scale=scale,
    )


def to_grayscale(
    image: np.ndarray,
) -> np.ndarray:
    """
    OpenCV画像をグレースケールへ変換する。

    すでにグレースケールの場合はコピーを返す。
    """
    _validate_image(image)

    if image.ndim == 2:
        return image.copy()

    if image.ndim == 3 and image.shape[2] == 3:
        return cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2GRAY,
        )

    raise ValueError(
        f"Unsupported image shape: {image.shape}"
    )


def _validate_image(
    image: np.ndarray,
) -> None:
    """
    入力画像を検証する。
    """
    if not isinstance(image, np.ndarray):
        raise TypeError(
            "image must be numpy.ndarray: "
            f"{type(image).__name__}"
        )

    if image.size == 0:
        raise ValueError("image is empty")

    if image.ndim not in (2, 3):
        raise ValueError(
            "image must be grayscale, BGR, or BGRA: "
            f"shape={image.shape}"
        )

    if image.ndim == 3 and image.shape[2] not in (3, 4):
        raise ValueError(
            "image must have 3 or 4 color channels: "
            f"shape={image.shape}"
        )


def _validate_scale(
    scale: float,
) -> None:
    """
    拡大倍率を検証する。
    """
    if not isinstance(scale, int | float):
        raise TypeError(
            "scale must be int or float: "
            f"{type(scale).__name__}"
        )

    if scale <= 0:
        raise ValueError(
            f"scale must be greater than 0: {scale}"
        )