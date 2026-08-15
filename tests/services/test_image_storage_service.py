import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from services.image_storage_service import (
    ImageStorageService,
)


@pytest.mark.asyncio
async def test_save_input_images(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
        retention_days=180,
    )

    image_bytes = b"test-image-data"

    saved_paths = await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="nia_final_grade_from_img",
        request_id="request-001",
        images={
            "schedule": (
                "schedule.PNG",
                image_bytes,
            ),
        },
        metadata={
            "status": "success",
        },
    )

    saved_path = Path(
        saved_paths["schedule"]
    )

    assert saved_path.exists()
    assert saved_path.read_bytes() == image_bytes
    assert saved_path.suffix == ".png"
    assert saved_path.parent.name == "456"
    assert saved_path.parent.parent.name == "123"


@pytest.mark.asyncio
async def test_save_multiple_input_images(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    saved_paths = await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="nia_required_score_from_img",
        request_id="request-002",
        images={
            "schedule": (
                "schedule.png",
                b"schedule-data",
            ),
            "party": (
                "party.jpg",
                b"party-data",
            ),
        },
    )

    assert set(saved_paths) == {
        "schedule",
        "party",
    }

    assert Path(
        saved_paths["schedule"]
    ).read_bytes() == b"schedule-data"

    assert Path(
        saved_paths["party"]
    ).read_bytes() == b"party-data"


@pytest.mark.asyncio
async def test_save_metadata_jsonl(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    saved_paths = await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="nia_final_grade_from_img",
        request_id="request-003",
        images={
            "schedule": (
                "schedule.png",
                b"image-data",
            ),
        },
        metadata={
            "status": "success",
            "ocr_result": {
                "vo": 1000,
            },
        },
    )

    saved_path = Path(
        saved_paths["schedule"]
    )
    metadata_path = (
        saved_path.parent / "metadata.jsonl"
    )

    assert metadata_path.exists()

    lines = metadata_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 1

    record = json.loads(lines[0])

    assert record["guild_id"] == 123
    assert record["user_id"] == 456
    assert (
        record["command_name"]
        == "nia_final_grade_from_img"
    )
    assert record["request_id"] == "request-003"
    assert record["retention_days"] == 180
    assert record["status"] == "success"
    assert record["ocr_result"] == {
        "vo": 1000,
    }
    assert (
        record["image_paths"]["schedule"]
        == saved_paths["schedule"]
    )


@pytest.mark.asyncio
async def test_unsupported_extension_uses_bin(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    saved_paths = await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="test_command",
        request_id="request-004",
        images={
            "schedule": (
                "schedule.gif",
                b"image-data",
            ),
        },
    )

    saved_path = Path(
        saved_paths["schedule"]
    )

    assert saved_path.suffix == ".bin"


@pytest.mark.asyncio
async def test_empty_request_id_raises_value_error(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="request_id must not be empty",
    ):
        await service.save_input_images(
            guild_id=123,
            user_id=456,
            command_name="test_command",
            request_id="",
            images={
                "schedule": (
                    "schedule.png",
                    b"image-data",
                ),
            },
        )


@pytest.mark.asyncio
async def test_empty_images_raises_value_error(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="images must not be empty",
    ):
        await service.save_input_images(
            guild_id=123,
            user_id=456,
            command_name="test_command",
            request_id="request-005",
            images={},
        )


@pytest.mark.asyncio
async def test_empty_image_data_raises_value_error(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(
        provided_directory=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="image data is empty",
    ):
        await service.save_input_images(
            guild_id=123,
            user_id=456,
            command_name="test_command",
            request_id="request-006",
            images={
                "schedule": (
                    "schedule.png",
                    b"",
                ),
            },
        )


@pytest.mark.asyncio
async def test_expired_directory_is_removed(
    tmp_path: Path,
) -> None:
    retention_days = 180

    expired_date = (
        datetime.now().date()
        - timedelta(days=retention_days + 1)
    )

    expired_directory = (
        tmp_path
        / expired_date.strftime("%Y-%m-%d")
    )
    expired_directory.mkdir()

    expired_file = (
        expired_directory / "old-image.png"
    )
    expired_file.write_bytes(b"old-image-data")

    service = ImageStorageService(
        provided_directory=tmp_path,
        retention_days=retention_days,
    )

    await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="test_command",
        request_id="request-007",
        images={
            "schedule": (
                "schedule.png",
                b"new-image-data",
            ),
        },
    )

    assert not expired_directory.exists()


@pytest.mark.asyncio
async def test_non_date_directory_is_not_removed(
    tmp_path: Path,
) -> None:
    unrelated_directory = (
        tmp_path / "manually-selected"
    )
    unrelated_directory.mkdir()

    service = ImageStorageService(
        provided_directory=tmp_path,
        retention_days=180,
    )

    await service.save_input_images(
        guild_id=123,
        user_id=456,
        command_name="test_command",
        request_id="request-008",
        images={
            "schedule": (
                "schedule.png",
                b"image-data",
            ),
        },
    )

    assert unrelated_directory.exists()