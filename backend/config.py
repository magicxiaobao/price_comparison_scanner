import os


class Settings:
    def __init__(self) -> None:
        self.HOST: str = "127.0.0.1"  # 固定绑定本地，禁止 0.0.0.0
        self.PORT: int = int(os.getenv("PORT", "17396"))
        self.SESSION_TOKEN: str = os.getenv("SESSION_TOKEN", "")
        self.DEV_MODE: bool = os.getenv("DEV_MODE", "").lower() in ("1", "true")
        self.APP_DATA_DIR: str = os.getenv("APP_DATA_DIR", os.path.expanduser("~/.price-comparison-scanner"))


settings = Settings()
