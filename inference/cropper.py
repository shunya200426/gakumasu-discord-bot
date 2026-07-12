"""
YOLOの検出座標を使用して画像を切り出すモジュール。

このモジュールでは、Bounding Boxの画像範囲内への補正、
余白の追加、不正な座標の検証を行う。
"""

from __future__ import annotations

import numpy as np

from inference.result import DetectionResult


def crop_detection(
    image: np.ndarray,
    detection: DetectionResult,
    *,
    padding: int = 0,
    copy: bool = True,
) -> np.ndarray:
    """
    DetectionResultの座標を使用して画像を切り出す。

    Args:
        image:
            OpenCVで扱うBGR形式の画像。
        detection:
            YOLOによる検出結果。
        padding:
            Bounding Boxの上下左右に追加する余白。
        copy:
            Trueの場合、元画像から独立したコピーを返す。
            Falseの場合、元画像のビューを返す。

    Returns:
        切り出したBGR画像。

    Raises:
        TypeError:
            imageがnumpy.ndarrayでない場合。
        ValueError:
            画像、padding、Bounding Boxが不正な場合。
    """
    _validate_image(image)
    _validate_padding(padding)

    image_height, image_width = image.shape[:2]

    x1, y1, x2, y2 = clamp_bbox(
        detection=detection,
        image_width=image_width,
        image_height=image_height,
        padding=padding,
    )

    cropped = image[y1:y2, x1:x2]

    if cropped.size == 0:
        raise ValueError(
            "Cropped image is empty: "
            f"class={detection.class_name}, "
            f"bbox=({x1}, {y1}, {x2}, {y2})"
        )

    return cropped.copy() if copy else cropped


def clamp_bbox(
    detection: DetectionResult,
    *,
    image_width: int,
    image_height: int,
    padding: int = 0,
) -> tuple[int, int, int, int]:
    """
    Bounding Boxに余白を追加し、画像範囲内へ補正する。

    Args:
        detection:
            YOLOによる検出結果。
        image_width:
            元画像の幅。
        image_height:
            元画像の高さ。
        padding:
            Bounding Boxの上下左右へ追加する余白。

    Returns:
        補正後の座標 `(x1, y1, x2, y2)`。

    Raises:
        ValueError:
            画像サイズまたは補正後のBounding Boxが不正な場合。
    """
    _validate_padding(padding)

    if image_width <= 0 or image_height <= 0:
        raise ValueError(
            "Image dimensions must be greater than 0: "
            f"width={image_width}, height={image_height}"
        )

    x1 = max(0, detection.x1 - padding)
    y1 = max(0, detection.y1 - padding)
    x2 = min(image_width, detection.x2 + padding)
    y2 = min(image_height, detection.y2 + padding)

    if x1 >= x2 or y1 >= y2:
        raise ValueError(
            "Invalid bounding box after clamping: "
            f"class={detection.class_name}, "
            f"original=({detection.x1}, {detection.y1}, "
            f"{detection.x2}, {detection.y2}), "
            f"clamped=({x1}, {y1}, {x2}, {y2}), "
            f"image_size=({image_width}, {image_height})"
        )

    return x1, y1, x2, y2


def crop_detections(
    image: np.ndarray,
    detections: tuple[DetectionResult, ...],
    *,
    padding: int = 0,
    copy: bool = True,
) -> dict[str, list[np.ndarray]]:
    """
    複数の検出結果をクラス名ごとに切り出す。

    Args:
        image:
            OpenCVで扱うBGR形式の画像。
        detections:
            YOLOによる検出結果一覧。
        padding:
            各Bounding Boxへ追加する余白。
        copy:
            Trueの場合、切り出し画像のコピーを返す。

    Returns:
        クラス名をキー、切り出し画像一覧を値とする辞書。

        例:
            {
                "vo_param": [image],
                "idol_icon": [image1, image2],
            }
    """
    cropped_by_class: dict[str, list[np.ndarray]] = {}

    for detection in detections:
        cropped = crop_detection(
            image=image,
            detection=detection,
            padding=padding,
            copy=copy,
        )

        cropped_by_class.setdefault(
            detection.class_name,
            [],
        ).append(cropped)

    return cropped_by_class


def _validate_image(image: np.ndarray) -> None:
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

    if image.ndim != 3:
        raise ValueError(
            "image must be a 3-dimensional BGR image: "
            f"shape={image.shape}"
        )

    if image.shape[2] != 3:
        raise ValueError(
            "image must have 3 color channels: "
            f"shape={image.shape}"
        )


def _validate_padding(padding: int) -> None:
    """
    Padding値を検証する。
    """
    if not isinstance(padding, int):
        raise TypeError(
            "padding must be int: "
            f"{type(padding).__name__}"
        )

    if padding < 0:
        raise ValueError(
            f"padding must be 0 or greater: {padding}"
        )