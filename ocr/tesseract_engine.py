"""
PyTessBaseAPIのライフサイクルとOCR実行を管理するモジュール。

Bot起動時に一度だけ初期化し、コマンド実行時には同じAPIを再利用する。
画像前処理やOCR結果の数値変換は、このモジュールでは行わない。
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from PIL import Image
from tesserocr import OEM, PSM, PyTessBaseAPI

from utils.logger import get_logger


logger = get_logger()


class TesseractEngine:
    """
    PyTessBaseAPIを保持し、OCR文字列を取得するクラス。

    PyTessBaseAPIはインスタンス生成時に一度だけ初期化し、
    close() が呼ばれるまで再利用する。
    """

    def __init__(
        self,
        *,
        language: str = "eng",
        page_segmentation_mode: PSM = PSM.SINGLE_LINE,
        engine_mode: OEM = OEM.LSTM_ONLY,
        tessdata_path: str | Path | None = None,
        default_whitelist: str | None = None,
        user_defined_dpi: int = 300,
    ) -> None:
        """
        Tesseract OCR APIを初期化する。

        Args:
            language:
                OCRに使用する言語。
            page_segmentation_mode:
                ページ分割モード。
                数値1行の読み取りではPSM.SINGLE_LINEを使用する。
            engine_mode:
                OCRエンジンモード。
            tessdata_path:
                tessdataディレクトリのパス。
                Noneの場合はシステム既定の場所を使用する。
            default_whitelist:
                初期状態で許可する文字。
                Noneの場合は文字種を制限しない。
            user_defined_dpi:
                Tesseractへ通知する画像DPI。

        Raises:
            FileNotFoundError:
                指定されたtessdataディレクトリが存在しない場合。
            ValueError:
                DPIなどの設定値が不正な場合。
        """
        if user_defined_dpi <= 0:
            raise ValueError(
                "user_defined_dpi must be greater than 0: "
                f"{user_defined_dpi}"
            )

        self._language = language
        self._psm = page_segmentation_mode
        self._oem = engine_mode
        self._default_whitelist = default_whitelist
        self._user_defined_dpi = user_defined_dpi
        self._closed = False

        # 同じPyTessBaseAPIを複数処理から同時利用しないためのロック
        self._lock = Lock()

        api_kwargs = {
            "lang": self._language,
            "psm": self._psm,
            "oem": self._oem,
        }

        self._tessdata_path: Path | None = None

        if tessdata_path is not None:
            path = Path(tessdata_path).expanduser().resolve()

            if not path.is_dir():
                raise FileNotFoundError(
                    f"tessdata directory does not exist: {path}"
                )

            self._tessdata_path = path
            api_kwargs["path"] = str(path)

        logger.info(
            "Initializing TesseractEngine: language=%s psm=%s oem=%s "
            "tessdata_path=%s",
            self._language,
            self._psm,
            self._oem,
            self._tessdata_path or "system default",
        )

        self._api = PyTessBaseAPI(**api_kwargs)

        self._set_variable(
            "user_defined_dpi",
            str(self._user_defined_dpi),
        )

        self._apply_whitelist(self._default_whitelist)

        logger.info("TesseractEngine initialized")

    @property
    def language(self) -> str:
        """使用中のOCR言語を返す。"""
        return self._language

    @property
    def page_segmentation_mode(self) -> PSM:
        """既定のページ分割モードを返す。"""
        return self._psm

    @property
    def is_closed(self) -> bool:
        """OCR APIが終了済みか判定する。"""
        return self._closed

    def recognize(
        self,
        image: np.ndarray | Image.Image,
        *,
        whitelist: str | None = None,
        page_segmentation_mode: PSM | None = None,
        strip: bool = True,
    ) -> str:
        """
        画像から文字列を取得する。

        Args:
            image:
                OpenCVのnumpy.ndarray、またはPillow画像。
                OpenCV画像はBGR・グレースケールの両方に対応する。
            whitelist:
                このOCR処理で許可する文字。
                Noneの場合は初期化時のdefault_whitelistを使用する。
            page_segmentation_mode:
                このOCR処理で使用するページ分割モード。
                Noneの場合は初期化時の値を使用する。
            strip:
                Trueの場合、結果の前後空白と改行を除去する。

        Returns:
            OCRで取得した生文字列。

        Raises:
            RuntimeError:
                close() 後に呼び出された場合。
            TypeError:
                未対応の画像型が渡された場合。
            ValueError:
                空画像や不正な画像が渡された場合。
        """
        self._ensure_open()

        pil_image = self._to_pil_image(image)

        active_whitelist = (
            self._default_whitelist
            if whitelist is None
            else whitelist
        )

        active_psm = (
            self._psm
            if page_segmentation_mode is None
            else page_segmentation_mode
        )

        # PyTessBaseAPIの同一インスタンスへ同時アクセスさせない
        with self._lock:
            self._ensure_open()

            try:
                self._api.SetPageSegMode(active_psm)
                self._apply_whitelist(active_whitelist)
                self._api.SetImage(pil_image)

                text = self._api.GetUTF8Text() or ""

            finally:
                # 現在の画像と認識結果を解放し、次のOCRへ備える
                self._api.Clear()

        return text.strip() if strip else text

    def recognize_digits(
        self,
        image: np.ndarray | Image.Image,
        *,
        allow_comma: bool = False,
    ) -> str:
        """
        数字に限定してOCRを実行する。

        Args:
            image:
                OCR対象画像。
            allow_comma:
                Trueの場合、カンマも許可する。

        Returns:
            OCRで取得した生文字列。

        Notes:
            数値への変換や不要文字の除去はparser.pyで行う。
        """
        whitelist = "0123456789"

        if allow_comma:
            whitelist += ","

        return self.recognize(
            image,
            whitelist=whitelist,
            page_segmentation_mode=PSM.SINGLE_LINE,
        )

    def recognize_percentage(
        self,
        image: np.ndarray | Image.Image,
    ) -> str:
        """
        小数・パーセント表記に限定してOCRを実行する。

        Returns:
            OCRで取得した生文字列。

        Notes:
            例: "13.9%"、"29%"
        """
        return self.recognize(
            image,
            whitelist="0123456789.%",
            page_segmentation_mode=PSM.SINGLE_LINE,
        )

    def close(self) -> None:
        """
        PyTessBaseAPIを終了する。

        複数回呼び出された場合、2回目以降は何もしない。
        """
        if self._closed:
            return

        with self._lock:
            if self._closed:
                return

            logger.info("Closing TesseractEngine")

            self._api.End()
            self._closed = True

            logger.info("TesseractEngine closed")

    def __enter__(self) -> TesseractEngine:
        """with文の開始時に自身を返す。"""
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """with文の終了時にOCR APIを終了する。"""
        self.close()

    def _apply_whitelist(
        self,
        whitelist: str | None,
    ) -> None:
        """
        Tesseractの文字ホワイトリストを設定する。

        Noneの場合は空文字列を設定し、文字種制限を解除する。
        """
        value = whitelist or ""

        self._set_variable(
            "tessedit_char_whitelist",
            value,
        )

    def _set_variable(
        self,
        name: str,
        value: str,
    ) -> None:
        """
        Tesseract変数を設定する。

        Raises:
            RuntimeError:
                変数の設定に失敗した場合。
        """
        success = self._api.SetVariable(name, value)

        if not success:
            raise RuntimeError(
                f"Failed to set Tesseract variable: "
                f"{name}={value!r}"
            )

    def _ensure_open(self) -> None:
        """
        APIが利用可能な状態か検証する。
        """
        if self._closed:
            raise RuntimeError(
                "TesseractEngine is already closed"
            )

    @staticmethod
    def _to_pil_image(
        image: np.ndarray | Image.Image,
    ) -> Image.Image:
        """
        OpenCV画像またはPillow画像を、Tesseractへ渡せる形式に変換する。
        """
        if isinstance(image, Image.Image):
            if image.width <= 0 or image.height <= 0:
                raise ValueError("Pillow image is empty")

            return image

        if not isinstance(image, np.ndarray):
            raise TypeError(
                "image must be numpy.ndarray or PIL.Image.Image: "
                f"{type(image).__name__}"
            )

        if image.size == 0:
            raise ValueError("image is empty")

        if image.ndim == 2:
            # グレースケール画像
            return Image.fromarray(image)

        if image.ndim == 3 and image.shape[2] == 3:
            # OpenCVのBGRからPillowのRGBへ変換
            rgb_image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB,
            )
            return Image.fromarray(rgb_image)

        if image.ndim == 3 and image.shape[2] == 4:
            # OpenCVのBGRAからPillowのRGBAへ変換
            rgba_image = cv2.cvtColor(
                image,
                cv2.COLOR_BGRA2RGBA,
            )
            return Image.fromarray(rgba_image)

        raise ValueError(
            "Unsupported image shape: "
            f"{image.shape}"
        )