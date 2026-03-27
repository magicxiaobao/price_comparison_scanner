import os


class Settings:
    HOST: str = "127.0.0.1"                          # 固定绑定本地，禁止 0.0.0.0
    PORT: int = int(os.getenv("PORT", "17396"))
    SESSION_TOKEN: str = os.getenv("SESSION_TOKEN", "")
    DEV_MODE: bool = os.getenv("DEV_MODE", "").lower() in ("1", "true")
    APP_DATA_DIR: str = os.getenv("APP_DATA_DIR", os.path.expanduser("~/.price-comparison-scanner"))


settings = Settings()
