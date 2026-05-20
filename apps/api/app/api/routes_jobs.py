from fastapi import APIRouter, Body, HTTPException
from uuid import uuid4
from pathlib import Path
import json

from app.core.config import DATA_DIR
from app.db.session import SessionLocal, init_db
from app.db.models import Job, Media, Transcript
from app.schemas.job import JobOut
from app.workers.pipeline import run_pipeline

router = APIRouter()


@router.post("")
def create_job(payload: dict = Body(...)):
    """
    Accepts:
      - { "media_id": 123 }
      - { "id": 123 }  (alias)
    """
    init_db()

    # Be flexible with payload shape (fixes 422 if client sends id instead of media_id)
    media_id = payload.get("media_id", None)
    if media_id is None:
        media_id = payload.get("id", None)

    if media_id is None:
        raise HTTPException(status_code=422, detail="Request body must include 'media_id' (or 'id').")

    try:
        media_id = int(media_id)
    except Exception:
        raise HTTPException(status_code=422, detail="'media_id' must be an integer.")

    db = SessionLocal()
    try:
        media = db.query(Media).filter(Media.id == media_id).first()
        if not media:
            raise HTTPException(status_code=404, detail="media not found")

        job_id = uuid4().hex
        job = Job(
            id=job_id,
            media_id=media.id,
            status="running",
            progress=0.01,
            message="starting",
            transcript_id="",
        )
        db.add(job)
        db.commit()

        run_dir = Path(DATA_DIR) / "runs" / job_id
        run_dir.mkdir(parents=True, exist_ok=True)

        def update(status, progress, message, transcript_id=""):
            j = db.query(Job).filter(Job.id == job_id).first()
            if not j:
                return
            j.status = status
            j.progress = float(progress)
            j.message = message
            if transcript_id:
                j.transcript_id = transcript_id
            db.commit()

        try:
            update("running", 0.05, "preprocessing")
            artifact = run_pipeline(Path(media.path), run_dir, update)
            transcript_id = artifact["transcript_id"]

            t = Transcript(
                id=transcript_id,
                media_id=media.id,
                language=artifact.get("language", "sv"),
                json_blob=json.dumps(artifact),
            )
            db.add(t)
            db.commit()

            update("done", 1.0, "complete", transcript_id=transcript_id)

        except Exception as e:
            update("error", 1.0, f"failed: {e}")

        out = db.query(Job).filter(Job.id == job_id).first()
        if not out:
            raise HTTPException(status_code=500, detail="job record missing after creation")

        return JobOut(
            id=out.id,
            status=out.status,
            progress=out.progress,
            message=out.message,
            transcript_id=out.transcript_id,
        )

    finally:
        db.close()


@router.get("/{job_id}")
def get_job(job_id: str):
    init_db()
    db = SessionLocal()
    try:
        out = db.query(Job).filter(Job.id == job_id).first()
        if not out:
            raise HTTPException(status_code=404, detail="job not found")

        return JobOut(
            id=out.id,
            status=out.status,
            progress=out.progress,
            message=out.message,
            transcript_id=out.transcript_id,
        )
    finally:
        db.close()