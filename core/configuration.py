from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base URL (e.g. "http://my.site") where this service is available at.
    # This will be used to construct full share URLs.
    base_http_url: str

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

    # Can be set to either "local" or "azure".
    # If set to "local", the "local_filesystem_base_directory" value must be specified.
    # If set to "azure", "azure_blob_storage_"-prefixed fields must be specified.
    storage_backend: str

    local_filesystem_base_directory: Optional[str]

    azure_blob_storage_url: Optional[str]
    azure_blob_storage_container_name: Optional[str]
    azure_blob_storage_shared_key: Optional[str]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
