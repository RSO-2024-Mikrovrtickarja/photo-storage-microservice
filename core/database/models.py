from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4


class Image(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    file_name: str

    file_path: str

    uploaded_at: datetime

    # ID of the owning user.
    owned_by_user_id: UUID


class ProcessingJob(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    job_name: str

    source_image_id: UUID = Field(foreign_key="image.id")

    # If this is non-null, the processing job is considered complete.
    # If this is null, the job is still in progress.
    destination_image_id: Optional[UUID] = Field(foreign_key="image.id")

    # Must be a JSON-serialized string of type `InternalImageProcessingJob`,
    # see `processing.py`.
    job_json_payload: str

    # A human-readable status.
    status: Optional[str]
