import os


class Settings:
    PROJECT_NAME: str = "Login API"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


settings = Settings()
