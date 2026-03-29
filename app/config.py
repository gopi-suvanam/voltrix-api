from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SHA-256 hex digest of the Bearer token.
    # Leave empty to disable auth (development only).
    api_token_hash: str = ""

    model_config = {"env_file": "config.env", "env_file_encoding": "utf-8"}


settings = Settings()
