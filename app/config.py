import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class AppSettings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./quizora.db",
    )
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET_KEY",
        "fallback_default_development_secret_signing_key_matrix",
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "quizora")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "quizora-users")
    FRONTEND_ORIGINS: list[str] = [
        origin.strip()
        for origin in (
            os.getenv("FRONTEND_ORIGINS")
            or "http://localhost:3000,http://127.0.0.1:3000,http://[::1]:3000"
        ).split(",")
        if origin.strip()
    ]
    FOLDER_STORAGE_DIR: Path = Path(
        os.getenv(
            "FOLDER_STORAGE_DIR",
            str(Path(__file__).resolve().parent / "folder_storage"),
        )
    ).resolve()


settings = AppSettings()
