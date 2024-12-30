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

    # Can be set to either "local" or "azure".
    # If set to "local", the "local_filesystem_base_directory" value must be specified.
    # If set to "azure", "azure_blob_storage_"-prefixed fields must be specified.
    storage_backend: str

    local_filesystem_base_directory: Optional[str] = None

    azure_blob_storage_url: Optional[str] = None
    azure_blob_storage_container_name: Optional[str] = None
    azure_blob_storage_shared_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
