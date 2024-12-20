import json
import threading
from typing import Annotated, Optional, Self
from fastapi import Depends
import zmq
from pydantic import BaseModel
from enum import Enum
import uuid

from core.configuration import settings

class ImageFormat(Enum):
    BLP = "BLP"
    BMP = "BMP"
    BUFR = "BUFR"
    DDS = "DDS"
    DIP = "DIB"
    EPS = "EPS"
    GIF = "GIF"
    GRIB = "GRIB"
    HDF5 = "HDF5"
    ICNS = "ICNS"
    ICO = "ICO"
    IM = "IM"
    JPEG = "JPEG"
    JPEG2000 = "JPEG2000"
    MPS = "MPS"
    PCX = "PCX"
    PNG = "PNG"
    PPM = "PPM"
    SGI = "SGI"
    SPIDER = "SPIDER"
    TGA = "TGA"
    TIFF = "TIFF"
    WEBP = "WEBP"
    WMF = "WMF"


class ImageProcessingJobStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._instances[cls]



class InternalImageProcessingJob(BaseModel):
    job_id: Optional[uuid.UUID]

    # This represents an image file path or S3 object name, 
    # depending on which storage backend is configured.
    image_path: str 

    # These are the actual processing parameters.
    resize_image_to_width: int
    resize_image_to_height: int
    change_to_format: str

class InternalImageProcessingJobConfirmation(BaseModel):
    is_ok: bool



# We shouldn't establish ZeroMQ REQ-REP connections each time
# a dependency is injected, but instead only the first time
# (after which the connection is persisted).
class ImageJobSubmitter(metaclass=Singleton):
    _zmq_context: zmq.Context
    _zmq_socket: zmq.Socket

    def __init__(self):
        print("Initializing image processing job submitter.")
        
        self._zmq_context = zmq.Context()

        self._zmq_socket = self._zmq_context.socket(zmq.REQ)
        self._zmq_socket.connect(f"tcp://{settings.zmq_host}:{settings.zmq_port}")


    def submit_processing_job(
        self,
        job: InternalImageProcessingJob
    ):
        serialized_job = job.model_dump_json()

        self._zmq_socket.send(serialized_job.encode("utf-8"))

        confirmation_reply_bytes = self._zmq_socket.recv()

        confirmation = InternalImageProcessingJobConfirmation.model_validate_json(
            confirmation_reply_bytes
        )

        if confirmation.is_ok is not True:
            raise Exception("Failed to obtain job confirmation.")
        else:
            print("Got job confirmation from worker.")



def get_image_job_submitter() -> ImageJobSubmitter:
    return ImageJobSubmitter()


JobSubmitterDependency = Annotated[ImageJobSubmitter, Depends(get_image_job_submitter)]
