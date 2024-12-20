from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Annotated, List, Optional, Self
import uuid
from tempfile import SpooledTemporaryFile
from fastapi import FastAPI, HTTPException, Path, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select
from mimetypes import guess_type
import uvicorn

from core.authentication import CurrentUserDependency
from core.database import SessionDependency, create_db_and_tables
from core.database.models import Image, ProcessingJob
from core.storage import StorageDependency
from core.processing import InternalImageProcessingJob, JobSubmitterDependency, ImageProcessingJobStatus, ImageFormat


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating database and tables...")
    create_db_and_tables()

    yield


app = FastAPI(lifespan=lifespan)

class PublicImage(BaseModel):
    id: uuid.UUID
    file_name: str
    uploaded_at: datetime

    @classmethod
    def from_database_image_model(
        cls,
        image: Image
    ) -> Self:
        return cls(
            id=image.id,
            file_name=image.file_name,
            uploaded_at=image.uploaded_at,
        )


class PublicImagesListResponse(BaseModel):
    images: List[PublicImage]


@app.get("/images")
def get_all_images_for_current_user(
    database: SessionDependency,
    current_user: CurrentUserDependency,
) -> PublicImagesListResponse:
    images_owned_by_current_user = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
    ).all()

    return {
        "images": [
            PublicImage.from_database_image_model(database_image)
            for database_image in images_owned_by_current_user
        ]
    }



class PublicSingleImageResponse(BaseModel):
    image: PublicImage


@app.get("/images/{image_id}")
def get_specific_image(
    database: SessionDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to get.")],
) -> PublicSingleImageResponse:
    target_image = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
            .where(Image.id == image_id)
    ).first()

    if target_image is None:
        raise HTTPException(status_code=404, detail="No such image.")
    
    return PublicSingleImageResponse(
        image=PublicImage.from_database_image_model(target_image)
    )
    



@app.post("/images")
def upload_new_image(
    database: SessionDependency,
    storage: StorageDependency,
    current_user: CurrentUserDependency,
    uploaded_file: UploadFile
) -> PublicSingleImageResponse:
    final_file_path = storage.upload_file(
        str(uploaded_file.filename),
        uploaded_file.file
    )

    new_image = Image(
        file_name=uploaded_file.filename,
        file_path=final_file_path,
        uploaded_at=datetime.now(tz=timezone.utc),
        owned_by_user_id=current_user.id
    )

    database.add(new_image)
    database.commit()
    database.refresh(new_image)

    
    return PublicSingleImageResponse(
        image=PublicImage.from_database_image_model(new_image)
    )


@app.delete("/images/{image_id}")
def delete_specific_image(
    database: SessionDependency,
    storage: StorageDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to delete.")],
):
    target_image = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
            .where(Image.id == image_id)
    ).one_or_none()

    if target_image is None:
        raise HTTPException(status_code=404, detail="No such image.")
    
    storage.delete_file(target_image.file_path)

    database.delete(target_image)
    database.commit()

    return { "ok": True }



@app.get("/images/{image_id}/download")
def download_specific_image(
    database: SessionDependency,
    storage: StorageDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to download.")],
):
    target_image = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
            .where(Image.id == image_id)
    ).one_or_none()

    if target_image is None:
        raise HTTPException(status_code=404, detail="No such image.")
    

    intermediate_image_buffer = SpooledTemporaryFile(mode="w+b")

    storage.download_file(target_image.file_path, intermediate_image_buffer)
    intermediate_image_buffer.seek(0, os.SEEK_SET)

    guessed_content_type = guess_type(target_image.file_name)[0] or "text/plain"

    return StreamingResponse(
        intermediate_image_buffer,
        status_code=200,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"attachment; filename=\"{target_image.file_name}\""
        },
        media_type=guessed_content_type
    )




class PublicImageProcessingJobRequest(BaseModel):
    job_name: str

    resize_image_to_width: int
    resize_image_to_height: int
    change_to_format: str


@app.post("/images/{image_id}/jobs")
def submit_new_processing_job(
    database: SessionDependency,
    current_user: CurrentUserDependency,
    job_submitter: JobSubmitterDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to submit the job for.")],
    processing_job_specification: PublicImageProcessingJobRequest
):
    source_image = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
            .where(Image.id == image_id)
    ).first()

    if source_image is None:
        raise HTTPException(status_code=404, detail="No such image.")

    if processing_job_specification.change_to_format not in set(img_format.value for img_format in ImageFormat):
        raise HTTPException(status_code=404, detail="Incorrect image format.")

    internal_job_specification = InternalImageProcessingJob(
        image_path=source_image.file_path,
        resize_image_to_width=processing_job_specification.resize_image_to_width,
        resize_image_to_height=processing_job_specification.resize_image_to_height,
        change_to_format=processing_job_specification.change_to_format,
        job_id=None,
    )

    serialized_internal_job_specification = internal_job_specification.model_dump_json()


    processing_job_model = ProcessingJob(
        job_name=processing_job_specification.job_name,
        source_image_id=source_image.id,
        destination_image_id=None,
        job_json_payload=serialized_internal_job_specification,
        status=None,
    )

    database.add(processing_job_model)
    internal_job_specification.job_id = processing_job_model.id
    job_submitter.submit_processing_job(internal_job_specification)

    database.commit()
    
    return { "ok": True }


class PublicImageJob(BaseModel):
    id: uuid.UUID

    job_name: str
    status: Optional[str]
    destination_image_id: Optional[uuid.UUID]
    job_json_payload: str

    @classmethod
    def from_database_job_model(
        cls,
        job: ProcessingJob
    ) -> Self:
        return cls(
            id=job.id,
            job_name=job.job_name,
            status=job.status,
            destination_image_id=job.destination_image_id,
            job_json_payload=job.job_json_payload
        )



class PublicImageJobListResponse(BaseModel):
    jobs: List[PublicImageJob]


@app.get("/images/{image_id}/jobs")
def get_all_image_jobs(
    database: SessionDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to get jobs for.")],
):
    all_relevant_image_jobs = database.exec(
        select(ProcessingJob)
            .where(ProcessingJob.source_image_id == image_id)
    ).all()

    public_image_job_models = [
        PublicImageJob.from_database_job_model(job)
        for job in all_relevant_image_jobs
    ]

    return PublicImageJobListResponse(
        jobs=public_image_job_models
    )




class APIImageSingleJobResponse(BaseModel):
    job: PublicImageJob


@app.get("/images/{image_id}/jobs/{job_id}")
def get_specific_image_job(
    database: SessionDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to get details for.")],
    job_id: Annotated[uuid.UUID, Path(title="The UUID of the job to get details for.")],
):
    target_image_job = database.exec(
        select(ProcessingJob)
            .where(ProcessingJob.source_image_id == image_id)
            .where(ProcessingJob.id == job_id)
    ).one_or_none()

    if target_image_job is None:
        raise HTTPException(status_code=404, detail="No such job.")
    
    return APIImageSingleJobResponse(
        job=PublicImageJob.from_database_job_model(target_image_job)
    )




@app.get("/worker/jobs/{job_id}/download-source-image")
def download_specific_image_to_worker(
    database: SessionDependency,
    storage: StorageDependency,
    job_id: Annotated[uuid.UUID, Path(title="The UUID of the job to finalize.")]
):

    source_image_job = database.exec(
        select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
    ).one_or_none()

    if source_image_job is None:
        raise HTTPException(status_code=404, detail="No such job.")

    source_image = database.exec(
        select(Image)
            .where(Image.id == source_image_job.source_image_id)
    ).one_or_none()

    if source_image is None:
        raise HTTPException(status_code=404, detail="No associated image.")

    intermediate_image_buffer = SpooledTemporaryFile(mode="w+b")

    storage.download_file(source_image.file_path, intermediate_image_buffer)
    intermediate_image_buffer.seek(0, os.SEEK_SET)

    guessed_content_type = guess_type(source_image.file_name)[0] or "text/plain"

    return StreamingResponse(
        intermediate_image_buffer,
        status_code=200,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"attachment; filename=\"{source_image.file_name}\""
        },
        media_type=guessed_content_type
    )


class PublicImageProcessingJobUpdateRequest(BaseModel):
    status: str


@app.patch("/worker/jobs/{job_id}")
def update_job_status_from_worker(
    database: SessionDependency,
    job_id: Annotated[uuid.UUID, Path(title="The UUID of the job to update details for.")],
    updated_details: PublicImageProcessingJobUpdateRequest,
):
    target_image_job = database.exec(
        select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
    ).one_or_none()

    if target_image_job is None:
        raise HTTPException(status_code=404, detail="No such job.")
    

    target_image_job.status = updated_details.status

    database.add(target_image_job)
    database.commit()

    return { "ok": True }


@app.post("/worker/jobs/{job_id}/finalize")
def upload_proceessed_image_from_worker(
    database: SessionDependency,
    storage: StorageDependency,
    job_id: Annotated[uuid.UUID, Path(title="The UUID of the job to finalize.")],
    uploaded_file: UploadFile
):
    source_image_job = database.exec(
        select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
    ).one_or_none()

    if source_image_job is None:
        raise HTTPException(status_code=404, detail="No such job.")


    source_image = database.exec(
        select(Image)
            .where(Image.id == source_image_job.source_image_id)
    ).one_or_none()

    if source_image is None:
        raise HTTPException(status_code=404, detail="No associated image.")


    final_file_path = storage.upload_file(
        str(uploaded_file.filename),
        uploaded_file.file
    )

    new_image = Image(
        file_name=uploaded_file.filename,
        file_path=final_file_path,
        uploaded_at=datetime.now(tz=timezone.utc),
        owned_by_user_id=source_image.owned_by_user_id
    )
    database.add(new_image)
    database.commit()
    database.refresh(new_image)


    source_image_job.destination_image_id = new_image.id
    database.add(source_image_job)
    database.commit()
    
    return PublicSingleImageResponse(
        image=PublicImage.from_database_image_model(new_image)
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
