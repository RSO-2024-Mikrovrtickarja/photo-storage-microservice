from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str

    jwt_secret_key: str
    jwt_algorithm: str

    storage_backend: str

    local_filesystem_base_directory: Optional[str]

    s3_service_url: Optional[str]
    s3_bucket: Optional[str]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
