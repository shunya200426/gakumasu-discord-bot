"""
推論処理およびOCR処理の結果を表すデータクラス。

このモジュールでは、YOLOの検出結果、OCRによる読み取り結果、
推論処理時間などを保持するための型を定義する。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class DetectionResult:
    """
    YOLOによる1件分の検出結果。

    Attributes:
        class_name:
            検出クラス名。
        confidence:
            検出信頼度。
        x1:
            Bounding Box左上のX座標。
        y1:
            Bounding Box左上のY座標。
        x2:
            Bounding Box右下のX座標。
        y2:
            Bounding Box右下のY座標。
    """

    class_name: str
    confidence: float

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Bounding Boxの幅を返す。"""
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Bounding Boxの高さを返す。"""
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        """Bounding Boxの面積を返す。"""
        return max(0, self.width) * max(0, self.height)

    @property
    def is_valid(self) -> bool:
        """Bounding Boxが有効な大きさを持つか判定する。"""
        return self.width > 0 and self.height > 0


@dataclass(slots=True, frozen=True)
class ParameterOcrResult:
    """
    スケジュール画像から読み取ったパラメータ情報。

    Attributes:
        vo:
            Voパラメータ。
        da:
            Daパラメータ。
        vi:
            Viパラメータ。
        fans:
            現在のファン数。
        star:
            スター性
    """

    vo: int | None = None
    da: int | None = None
    vi: int | None = None
    fans: int | None = None
    star: int | None = None

    def is_complete(
        self,
        *,
        require_star: bool = False,
    ) -> bool:
        return not self.missing_fields(
            require_star=require_star,
        )


    def missing_fields(
        self,
        *,
        require_star: bool = False,
    ) -> tuple[str, ...]:
        fields = {
            "vo": self.vo,
            "da": self.da,
            "vi": self.vi,
            "fans": self.fans,
        }

        if require_star:
            fields["star"] = self.star

        return tuple(
            name
            for name, value in fields.items()
            if value is None
        )


@dataclass(slots=True, frozen=True)
class BonusOcrResult:
    """
    編成画像から読み取ったパラメータボーナス情報。

    Attributes:
        vo:
            Voパラメータボーナス。
        da:
            Daパラメータボーナス。
        vi:
            Viパラメータボーナス。
        kirameki:
            ほしのきらめき。
            強化月間でない場合はNoneを許容する。
    """

    vo: float | None = None
    da: float | None = None
    vi: float | None = None
    kirameki: int | None = None

    def is_complete(
        self,
        *,
        require_kirameki: bool = False,
    ) -> bool:
        """
        必要なすべての値を取得できているか判定する。

        Args:
            require_kirameki:
                Trueの場合、きらめきも必須項目として判定する。
        """
        return not self.missing_fields(
            require_kirameki=require_kirameki,
        )

    def missing_fields(
        self,
        *,
        require_kirameki: bool = False,
    ) -> tuple[str, ...]:
        """
        読み取りに失敗した項目名を返す。

        Args:
            require_kirameki:
                Trueの場合、きらめきも判定対象に含める。
        """
        fields: dict[str, float | int | None] = {
            "vo": self.vo,
            "da": self.da,
            "vi": self.vi,
        }

        if require_kirameki:
            fields["kirameki"] = self.kirameki

        return tuple(
            name
            for name, value in fields.items()
            if value is None
        )


@dataclass(slots=True, frozen=True)
class ScoreOcrResult:
    """
    スコア画像から読み取ったオーディションスコア情報。

    Attributes:
        sum_score:
            画面に表示されている合計スコア。
        vo:
            Voスコア。
        da:
            Daスコア。
        vi:
            Viスコア。
    """

    sum_score: int | None = None
    vo: int | None = None
    da: int | None = None
    vi: int | None = None

    @property
    def is_complete(self) -> bool:
        """必要なすべての値を取得できているか判定する。"""
        return not self.missing_fields

    @property
    def missing_fields(self) -> tuple[str, ...]:
        """読み取りに失敗した項目名を返す。"""
        fields = {
            "sum_score": self.sum_score,
            "vo": self.vo,
            "da": self.da,
            "vi": self.vi,
        }

        return tuple(
            name
            for name, value in fields.items()
            if value is None
        )

    @property
    def calculated_sum(self) -> int | None:
        """
        Vo・Da・Viから計算した合計値を返す。

        いずれかがNoneの場合はNoneを返す。
        """
        if self.vo is None or self.da is None or self.vi is None:
            return None

        return self.vo + self.da + self.vi

    @property
    def is_sum_consistent(self) -> bool:
        """
        表示上の合計スコアとVo・Da・Viの合計が一致するか判定する。

        必要な値が不足している場合はFalseを返す。
        """
        calculated_sum = self.calculated_sum

        if self.sum_score is None or calculated_sum is None:
            return False

        return self.sum_score == calculated_sum


@dataclass(slots=True, frozen=True)
class InferenceResult:
    """
    YOLO推論とOCR処理をまとめた最終結果。

    Attributes:
        parameters:
            パラメータ・ファン数のOCR結果。
        bonuses:
            パラメータボーナス・きらめきのOCR結果。
        scores:
            オーディションスコアのOCR結果。
        detections:
            YOLOによる検出結果一覧。
        image_width:
            入力画像の幅。
        image_height:
            入力画像の高さ。
        preprocess_ms:
            前処理時間。
        inference_ms:
            YOLO推論時間。
        postprocess_ms:
            切り出し・OCRなどの後処理時間。
        total_ms:
            処理全体の時間。
    """

    parameters: ParameterOcrResult
    bonuses: BonusOcrResult
    scores: ScoreOcrResult

    detections: tuple[DetectionResult, ...] = field(
        default_factory=tuple,
    )

    image_width: int = 0
    image_height: int = 0

    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0

    def is_complete(
        self,
        *,
        require_star: bool = False,
        require_kirameki: bool = False,
    ) -> bool:
        """
        推論結果に必要な値がすべて含まれているか判定する。

        Args:
            require_kirameki:
                Trueの場合、きらめきも必須項目として判定する。
        """
        return (
            self.parameters.is_complete(
                require_star=require_star,
            )
            and self.bonuses.is_complete(
                require_kirameki=require_kirameki,
            )
            and self.scores.is_complete
        )

    def missing_fields(
        self,
        *,
        require_star: bool = False,
        require_kirameki: bool = False,
    ) -> tuple[str, ...]:
        """
        読み取りに失敗した項目名を名前空間付きで返す。

        Returns:
            例:
                (
                    "parameters.fans",
                    "bonuses.vi",
                    "scores.vo",
                )
        """
        missing: list[str] = []

        missing.extend(
            f"parameters.{name}"
            for name in self.parameters.missing_fields(
                require_star=require_star,
            )
        )

        missing.extend(
            f"bonuses.{name}"
            for name in self.bonuses.missing_fields(
                require_kirameki=require_kirameki,
            )
        )

        missing.extend(
            f"scores.{name}"
            for name in self.scores.missing_fields
        )

        return tuple(missing)