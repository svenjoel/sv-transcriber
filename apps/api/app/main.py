import warnings

warnings.filterwarnings("ignore", module="pyannote")
warnings.filterwarnings("ignore", module="speechbrain")
warnings.filterwarnings("ignore", module="torchaudio")


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_media import router as media_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_transcripts import router as transcripts_router
from app.api.routes_speakers import router as speakers_router

app = FastAPI(title="sv-transcriber API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media_router, prefix="/media", tags=["media"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(transcripts_router, prefix="/transcripts", tags=["transcripts"])
app.include_router(speakers_router, prefix="/speakers", tags=["speakers"])  # ✅ NEW

@app.get("/health")
def health():
    return {"status": "ok"}