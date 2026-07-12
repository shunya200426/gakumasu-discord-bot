"""
OCR処理全体を統括するサービス。

YOLOによって切り出された画像を受け取り、
画像前処理・OCR実行・文字列解析を組み合わせて、
Bot内部で使用するOCR結果へ変換する。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from inference.result import (
    BonusOcrResult,
    ParameterOcrResult,
    ScoreOcrResult,
)
from ocr.parser import (
    parse_integer,
    parse_percentage,
)
from ocr.preprocess import (
    preprocess_fans,
    preprocess_kirameki,
    preprocess_parameter,
    preprocess_percentage,
    preprocess_score,
)
from ocr.tesseract_engine import TesseractEngine
from utils.logger import get_logger


logger = get_logger()


CroppedImages = Mapping[str, Sequence[np.ndarray]]


class OcrService:
    """
    OCRに必要な前処理・文字認識・数値変換を統括するクラス。

    TesseractEngineの生成や終了は担当せず、
    外部から渡されたエンジンを再利用する。
    """

    def __init__(
        self,
        engine: TesseractEngine,
    ) -> None:
        """
        OcrServiceを初期化する。

        Args:
            engine:
                OCRに使用するTesseractEngine。
                Bot起動中は同じインスタンスを再利用する。
        """
        if not isinstance(engine, TesseractEngine):
            raise TypeError(
                "engine must be TesseractEngine: "
                f"{type(engine).__name__}"
            )

        self._engine = engine

    @property
    def engine(self) -> TesseractEngine:
        """使用中のTesseractEngineを返す。"""
        return self._engine

    def read_parameters(
        self,
        cropped_by_class: CroppedImages,
        *,
        maximum: int,
        star_maximum: int | None = None,
    ) -> ParameterOcrResult:
        """
        Vo・Da・Viパラメータとファン数を読み取る。

        Args:
            cropped_by_class:
                クラス名ごとに整理された切り抜き画像。
            maximum:
                Vo・Da・Viパラメータの最大値。
            star_maximum:
                スター性の最大値。
                Noneの場合は上限を設定しない。

        Returns:
            読み取り結果。
            画像が存在しない、または読み取りに失敗した項目はNone。
        """
        self._validate_cropped_images(cropped_by_class)
        self._validate_maximum(maximum)

        if star_maximum is not None:
            self._validate_maximum(star_maximum)

        vo = self._read_parameter(
            cropped_by_class,
            class_name="vo_param",
            maximum=maximum,
        )
        da = self._read_parameter(
            cropped_by_class,
            class_name="da_param",
            maximum=maximum,
        )
        vi = self._read_parameter(
            cropped_by_class,
            class_name="vi_param",
            maximum=maximum,
        )
        fans = self._read_fans(
            cropped_by_class,
            class_name="fan_count",
        )
        star = self._read_parameter(
            cropped_by_class,
            class_name="star_param",
            maximum=star_maximum,
        )

        result = ParameterOcrResult(
            vo=vo,
            da=da,
            vi=vi,
            fans=fans,
            star=star,
        )

        logger.debug(
            "Parameter OCR completed: "
            "vo=%s da=%s vi=%s fans=%s star=%s",
            result.vo,
            result.da,
            result.vi,
            result.fans,
            result.star,
        )

        return result

    def read_bonuses(
        self,
        cropped_by_class: CroppedImages,
    ) -> BonusOcrResult:
        """
        Vo・Da・Viボーナスとほしのきらめきを読み取る。

        Args:
            cropped_by_class:
                クラス名ごとに整理された切り抜き画像。

        Returns:
            読み取り結果。
            画像が存在しない、または読み取りに失敗した項目はNone。
        """
        self._validate_cropped_images(cropped_by_class)

        vo = self._read_percentage(
            cropped_by_class,
            class_name="vo_bonus",
        )
        da = self._read_percentage(
            cropped_by_class,
            class_name="da_bonus",
        )
        vi = self._read_percentage(
            cropped_by_class,
            class_name="vi_bonus",
        )
        kirameki = self._read_kirameki(
            cropped_by_class,
            class_name="kirameki",
        )

        result = BonusOcrResult(
            vo=vo,
            da=da,
            vi=vi,
            kirameki=kirameki,
        )

        logger.debug(
            "Bonus OCR completed: vo=%s da=%s vi=%s kirameki=%s",
            result.vo,
            result.da,
            result.vi,
            result.kirameki,
        )

        return result

    def read_scores(
        self,
        cropped_by_class: CroppedImages,
    ) -> ScoreOcrResult:
        """
        合計スコアとVo・Da・Viスコアを読み取る。

        Args:
            cropped_by_class:
                クラス名ごとに整理された切り抜き画像。

        Returns:
            読み取り結果。
            画像が存在しない、または読み取りに失敗した項目はNone。
        """
        self._validate_cropped_images(cropped_by_class)

        sum_score = self._read_score(
            cropped_by_class,
            class_name="exam_score",
        )
        vo = self._read_score(
            cropped_by_class,
            class_name="vo_score",
        )
        da = self._read_score(
            cropped_by_class,
            class_name="da_score",
        )
        vi = self._read_score(
            cropped_by_class,
            class_name="vi_score",
        )

        result = ScoreOcrResult(
            sum_score=sum_score,
            vo=vo,
            da=da,
            vi=vi,
        )

        logger.debug(
            "Score OCR completed: sum=%s vo=%s da=%s vi=%s "
            "consistent=%s",
            result.sum_score,
            result.vo,
            result.da,
            result.vi,
            result.is_sum_consistent,
        )

        return result

    def _read_parameter(
        self,
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
        maximum: int,
    ) -> int | None:
        """
        1つのパラメータ値を読み取る。
        """
        image = self._get_first_image(
            cropped_by_class,
            class_name=class_name,
        )

        if image is None:
            return None

        processed = preprocess_parameter(image)

        text = self._engine.recognize_digits(
            processed,
        )

        value = parse_integer(
            text,
            minimum=0,
            maximum=maximum,
        )

        self._log_ocr_result(
            class_name=class_name,
            raw_text=text,
            parsed_value=value,
        )

        return value

    def _read_fans(
        self,
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
    ) -> int | None:
        """
        ファン数を読み取る。
        """
        image = self._get_first_image(
            cropped_by_class,
            class_name=class_name,
        )

        if image is None:
            return None

        processed = preprocess_fans(image)

        text = self._engine.recognize_digits(
            processed,
            allow_comma=True,
        )

        value = parse_integer(
            text,
            allow_comma=True,
            minimum=0,
        )

        self._log_ocr_result(
            class_name=class_name,
            raw_text=text,
            parsed_value=value,
        )

        return value

    def _read_percentage(
        self,
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
    ) -> float | None:
        """
        パラメータボーナスを読み取る。
        """
        image = self._get_first_image(
            cropped_by_class,
            class_name=class_name,
        )

        if image is None:
            return None

        processed = preprocess_percentage(image)

        text = self._engine.recognize_percentage(
            processed,
        )

        value = parse_percentage(
            text,
            require_percent_sign=False,
            return_ratio=False,
            minimum=0.0,
        )

        self._log_ocr_result(
            class_name=class_name,
            raw_text=text,
            parsed_value=value,
        )

        return value

    def _read_kirameki(
        self,
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
    ) -> int | None:
        """
        ほしのきらめきを読み取る。
        """
        image = self._get_first_image(
            cropped_by_class,
            class_name=class_name,
        )

        if image is None:
            return None

        processed = preprocess_kirameki(image)

        text = self._engine.recognize_digits(
            processed,
        )

        value = parse_integer(
            text,
            minimum=0,
        )

        self._log_ocr_result(
            class_name=class_name,
            raw_text=text,
            parsed_value=value,
        )

        return value

    def _read_score(
        self,
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
    ) -> int | None:
        """
        オーディションスコアを読み取る。
        """
        image = self._get_first_image(
            cropped_by_class,
            class_name=class_name,
        )

        if image is None:
            return None

        processed = preprocess_score(image)

        text = self._engine.recognize_digits(
            processed,
            allow_comma=True,
        )

        value = parse_integer(
            text,
            allow_comma=True,
            minimum=0,
        )

        self._log_ocr_result(
            class_name=class_name,
            raw_text=text,
            parsed_value=value,
        )

        return value

    @staticmethod
    def _get_first_image(
        cropped_by_class: CroppedImages,
        *,
        class_name: str,
    ) -> np.ndarray | None:
        """
        指定クラスの最初の切り抜き画像を取得する。

        対象クラスが存在しない場合はNoneを返す。
        """
        images = cropped_by_class.get(class_name)

        if not images:
            logger.debug(
                "OCR target image not found: class=%s",
                class_name,
            )
            return None

        image = images[0]

        if not isinstance(image, np.ndarray):
            raise TypeError(
                "cropped image must be numpy.ndarray: "
                f"class={class_name}, "
                f"type={type(image).__name__}"
            )

        if image.size == 0:
            raise ValueError(
                f"cropped image is empty: class={class_name}"
            )

        if len(images) > 1:
            logger.warning(
                "Multiple OCR target images found; "
                "using the first image: class=%s count=%d",
                class_name,
                len(images),
            )

        return image

    @staticmethod
    def _validate_cropped_images(
        cropped_by_class: CroppedImages,
    ) -> None:
        """
        切り抜き画像辞書を検証する。
        """
        if not isinstance(cropped_by_class, Mapping):
            raise TypeError(
                "cropped_by_class must be Mapping: "
                f"{type(cropped_by_class).__name__}"
            )

    @staticmethod
    def _validate_maximum(maximum: int) -> None:
        """
        パラメータ最大値を検証する。
        """
        if not isinstance(maximum, int):
            raise TypeError(
                "maximum must be int: "
                f"{type(maximum).__name__}"
            )

        if maximum <= 0:
            raise ValueError(
                f"maximum must be greater than 0: {maximum}"
            )

    @staticmethod
    def _log_ocr_result(
        *,
        class_name: str,
        raw_text: str,
        parsed_value: int | float | None,
    ) -> None:
        """
        OCRの生文字列と変換結果をデバッグログへ記録する。
        """
        logger.debug(
            "OCR result: class=%s raw=%r parsed=%s",
            class_name,
            raw_text,
            parsed_value,
        )