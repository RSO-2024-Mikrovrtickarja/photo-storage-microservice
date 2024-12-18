from datetime import datetime
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

    json_job_payload: str
