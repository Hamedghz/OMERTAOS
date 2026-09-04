import pytest

from control.config import Settings


DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "OMERTA_CONTROL_CORS_ORIGINS",
        "AION_CONTROL_CORS_ORIGINS",
        "OMERTA_CORS_ORIGINS",
        "AION_CORS_ORIGINS",
        "CORS_ORIGINS",
        "OMERTA_CONSOLE_ORIGIN",
        "AION_CONSOLE_ORIGIN",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, DEFAULT_ORIGINS),
        ("", DEFAULT_ORIGINS),
        ("*", ["*"]),
        ("http://localhost:3001", ["http://localhost:3001"]),
        (
            "http://localhost:3000,http://localhost:3001",
            ["http://localhost:3000", "http://localhost:3001"],
        ),
        (
            '["http://localhost:3000","http://localhost:3001"]',
            ["http://localhost:3000", "http://localhost:3001"],
        ),
    ],
)

def test_cors_origins_parsing(monkeypatch: pytest.MonkeyPatch, value: str | None, expected):
    clear_env(monkeypatch)
    if value is not None:
        monkeypatch.setenv("OMERTA_CONTROL_CORS_ORIGINS", value)

    settings = Settings()

    assert settings.cors_origins == expected


def test_cors_origins_alias(monkeypatch: pytest.MonkeyPatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:9000")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:9000"]


def test_cors_origins_legacy_alias(monkeypatch: pytest.MonkeyPatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("AION_CONTROL_CORS_ORIGINS", "http://localhost:9001")

    with pytest.warns(UserWarning, match="AION_CONTROL_CORS_ORIGINS"):
        settings = Settings()

    assert settings.cors_origins == ["http://localhost:9001"]



def test_cors_origins_invalid(monkeypatch: pytest.MonkeyPatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("OMERTA_CONTROL_CORS_ORIGINS", "[invalid]")

    settings = Settings()

    assert settings.cors_origins == DEFAULT_ORIGINS
