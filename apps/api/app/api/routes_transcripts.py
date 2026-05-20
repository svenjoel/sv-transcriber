from fastapi import APIRouter
import json

from app.db.session import SessionLocal, init_db
from app.db.models import Transcript

router = APIRouter()

@router.get("/{transcript_id}")
def get_transcript(transcript_id: str):
    init_db()
    db = SessionLocal()
    t = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not t:
        db.close()
        return {"error": "not found"}
    artifact = json.loads(t.json_blob)
    db.close()
    return artifact

@router.put("/{transcript_id}/rename-speaker")
def rename_speaker(transcript_id: str, speaker: str, name: str):
    # Rename a speaker label within ONE transcript artifact.
    init_db()
    db = SessionLocal()
    t = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not t:
        db.close()
        return {"error": "not found"}
    artifact = json.loads(t.json_blob)
    for seg in artifact.get("segments", []):
        if seg.get("speaker") == speaker:
            seg["speaker_name"] = name
    t.json_blob = json.dumps(artifact)
    db.commit()
    db.close()
    return {"ok": True}
