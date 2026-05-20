from pydantic import BaseModel

class JobCreate(BaseModel):
    media_id: int

class JobOut(BaseModel):
    id: str
    status: str
    progress: float
    message: str
    transcript_id: str
