from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Annotated, BinaryIO
from fastapi import Depends
from azure.storage.blob import BlobServiceClient, ContainerClient

from .configuration import settings


class BaseFileStorage(metaclass=ABCMeta):
    @abstractmethod
    def download_file(self, name: str, writable: BinaryIO):
        return NotImplemented
    
    @abstractmethod
    def upload_file(self, name: str, readable: BinaryIO):
        return NotImplemented
    
    @abstractmethod
    def delete_file(self, name: str):
        return NotImplemented



class LocalFileSystemStorage(BaseFileStorage):
    _base_directory: Path

    def __init__(self):
        super().__init__()

        if settings.local_filesystem_base_directory is None:
            raise RuntimeError(
                "Invalid configuration: storage backend is set to local, \
                 but local_filesystem_base_directory is unset"
            )

        self._base_directory = Path(settings.local_filesystem_base_directory).resolve()

    def download_file(self, file_name: str, writable: BinaryIO):
        file_name_only = Path(file_name).name
        full_file_path: Path = self._base_directory / file_name_only

        with full_file_path.open("rb") as file:
            writable.write(file.read())

    def upload_file(self, file_name: str, readable: BinaryIO) -> str:
        file_name_only = Path(file_name).name
        full_file_path: Path = self._base_directory / file_name_only

        with full_file_path.open("wb") as file:
            file.write(readable.read())
        
        return full_file_path.name
    
    def delete_file(self, file_name: str):
        file_name_only = Path(file_name).name
        full_file_path: Path = self._base_directory / file_name_only

        full_file_path.unlink(missing_ok=False)
        



class AzureBlobStorage(BaseFileStorage):
    _azure_client: BlobServiceClient
    _blob_container: ContainerClient

    def __init__(self):
        super().__init__()

        if settings.azure_blob_storage_shared_key is None:
            raise RuntimeError(
                "Invalid configuration: storage backend is set to azure, \
                 but azure_blob_storage_shared_key is unset"
            )
        
        if settings.azure_blob_storage_url is None:
            raise RuntimeError(
                "Invalid configuration: storage backend is set to azure, \
                 but azure_blob_storage_url is unset"
            )
        
        if settings.azure_blob_storage_container_name is None:
            raise RuntimeError(
                "Invalid configuration: storage backend is set to azure, \
                 but azure_blob_storage_container_name is unset"
            )
        
        self._azure_client = BlobServiceClient(
            account_url=settings.azure_blob_storage_url,
            credential=settings.azure_blob_storage_shared_key
        )

        self._blob_container = self._azure_client.get_container_client(settings.azure_blob_storage_container_name)


    def download_file(self, object_name: str, writable: BinaryIO):
        blob_client = self._blob_container.get_blob_client(blob=object_name)
        file_reader = blob_client.download_blob()

        writable.write(file_reader.readall())
        writable.seek(0)
    
    def upload_file(self, object_id: str, readable: BinaryIO) -> str:
        blob_client = self._blob_container.get_blob_client(blob=object_id)
        blob_client.upload_blob(data=readable.read())

        return object_id
    
    def delete_file(self, object_id: str):
        blob_client = self._blob_container.get_blob_client(blob=object_id)
        blob_client.delete_blob()



def get_storage_instance() -> BaseFileStorage:
    storage_backend: str = settings.storage_backend.lower()

    if storage_backend == "local":
        return LocalFileSystemStorage()
    elif storage_backend == "azure":
        return AzureBlobStorage()
    else:
        raise RuntimeError(
            "Invalid storage_backend configuration value: \
             expected either \"local\" or \"azure\"."
        )

StorageDependency = Annotated[BaseFileStorage, Depends(get_storage_instance)]
