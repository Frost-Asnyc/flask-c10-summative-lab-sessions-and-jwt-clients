import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///shifts.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
