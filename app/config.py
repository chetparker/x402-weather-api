from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Weather Data API"
    app_version: str = "1.0.0"
    x402_facilitator_url: str = "https://api.cdp.coinbase.com/platform/v2/x402"
    payment_wallet_address: str = ""
    price_per_request: str = "0.001"
    log_level: str = "INFO"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
