from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, List, Self
import uuid
from fastapi import Depends, FastAPI, HTTPException, Path, UploadFile
from pydantic import BaseModel
from sqlmodel import select
import uvicorn

from core.authentication import TokenData, CurrentUserDependency
from core.database import SessionDependency, create_db_and_tables
from core.database.models import Image, ProcessingJob
from core.storage import StorageDependency


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating database and tables...")
    create_db_and_tables()

    yield


app = FastAPI(lifespan=lifespan)

class APIImage(BaseModel):
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


class APIImagesResponse(BaseModel):
    images: List[APIImage]


@app.get("/images")
def get_all_images_for_current_user(
    database: SessionDependency,
    current_user: CurrentUserDependency,
) -> APIImagesResponse:
    images_owned_by_current_user = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
    ).all()

    return {
        "images": [
            APIImage.from_database_image_model(database_image)
            for database_image in images_owned_by_current_user
        ]
    }



class APISingleImageResponse(BaseModel):
    image: APIImage


@app.get("/images/{image_id}")
def get_specific_image(
    database: SessionDependency,
    current_user: CurrentUserDependency,
    image_id: Annotated[uuid.UUID, Path(title="The UUID of the image to get.")],
) -> APISingleImageResponse:
    target_image = database.exec(
        select(Image)
            .where(Image.owned_by_user_id == current_user.id)
            .where(Image.id == image_id)
    ).first()

    if target_image is None:
        raise HTTPException(status_code=404, detail="No such image.")
    
    return APISingleImageResponse(
        image=APIImage.from_database_image_model(target_image)
    )
    



@app.post("/images")
def upload_new_image(
    database: SessionDependency,
    storage: StorageDependency,
    current_user: CurrentUserDependency,
    uploaded_file: UploadFile
) -> APISingleImageResponse:
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

    
    return APISingleImageResponse(
        image=APIImage.from_database_image_model(new_image)
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
    ).first()

    if target_image is None:
        raise HTTPException(status_code=404, detail="No such image.")
    
    storage.delete_file(target_image.file_path)

    database.delete(target_image)
    database.commit()

    return { "ok": True }



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
