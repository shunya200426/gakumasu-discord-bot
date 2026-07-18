"""GakumasuBotのImageConsentService初期化テスト。"""

from __future__ import annotations

import ast
from pathlib import Path


MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


def get_gakumasu_bot_class() -> ast.ClassDef:
    module = ast.parse(
        MAIN_PATH.read_text(encoding="utf-8")
    )
    return next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef)
        and node.name == "GakumasuBot"
    )


def test_bot_declares_image_consent_service() -> None:
    bot_class = get_gakumasu_bot_class()
    initializer = next(
        node
        for node in bot_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "__init__"
    )

    assignment = next(
        node
        for node in ast.walk(initializer)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Attribute)
        and node.target.attr == "image_consent_service"
    )

    assert isinstance(assignment.value, ast.Constant)
    assert assignment.value.value is None


def test_setup_hook_uses_existing_user_repository_before_commands() -> None:
    bot_class = get_gakumasu_bot_class()
    setup_hook = next(
        node
        for node in bot_class.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "setup_hook"
    )

    assignment = next(
        node
        for node in ast.walk(setup_hook)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "image_consent_service"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Call)
    assert isinstance(assignment.value.func, ast.Name)
    assert assignment.value.func.id == "ImageConsentService"

    repository_keyword = next(
        keyword
        for keyword in assignment.value.keywords
        if keyword.arg == "user_repository"
    )
    assert isinstance(repository_keyword.value, ast.Attribute)
    assert isinstance(repository_keyword.value.value, ast.Name)
    assert repository_keyword.value.value.id == "db"
    assert repository_keyword.value.attr == "users"

    command_registration = next(
        node
        for node in ast.walk(setup_hook)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name)
        and node.iter.id == "MODULES"
    )
    assert assignment.lineno < command_registration.lineno


def test_setup_hook_does_not_create_database_connection() -> None:
    bot_class = get_gakumasu_bot_class()
    setup_hook = next(
        node
        for node in bot_class.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "setup_hook"
    )

    called_names = {
        node.func.id
        for node in ast.walk(setup_hook)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }

    assert "DatabaseManager" not in called_names
    assert "sqlite3" not in called_names

