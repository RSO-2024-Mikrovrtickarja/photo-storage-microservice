from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Configures the connection to the PostgreSQL database.
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str

    # Configures the Json Web Token secrets and other parameters.
    # This should match the settings on the user authentication microservice.
    jwt_secret_key: str
    jwt_algorithm: str

    # Configures the ZeroMQ messaging system that 
    # is connected to the worker.
    zmq_host: str
    zmq_port: int

    # Can be set to either "local" or "s3".
    # If set to "local", the "local_filesystem_base_directory" value must be specified.
    # If set to "s3", "s3_service_url" and "s3_bucket" must be specified.
    storage_backend: str

    local_filesystem_base_directory: Optional[str]

    s3_service_url: Optional[str]
    s3_bucket: Optional[str]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()