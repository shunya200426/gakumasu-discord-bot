from pathlib import Path

from discord import ui


def build_error_container(
    *, values: dict, error_reason: str | None = None
) -> ui.Container:
    template = Path(__file__).with_name("err_template.md").read_text(encoding="utf-8")
    fields = {
        key: "__未取得__" if values.get(key) is None else str(values[key])
        for key in (
            "vo_status",
            "da_status",
            "vi_status",
            "mid_exam_score",
            "final_exam_score",
        )
    }
    container = ui.Container(accent_color=0xE67E22)
    container.add_item(
        ui.TextDisplay(template.format(**fields, error_reason=error_reason or ""))
    )
    return container
