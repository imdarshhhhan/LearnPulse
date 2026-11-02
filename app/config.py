import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class AppSettings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./learnpulse.db",
    )
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET_KEY",
        "fallback_default_development_secret_signing_key_matrix",
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "learnpulse")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "learnpulse-users")
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
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")



settings = AppSettings()
