from fastapi import APIRouter
from app.db.session import SessionLocal, init_db
from app.db.models import SpeakerProfile
import json

router = APIRouter()

@router.get("")
def list_speakers():
    init_db()
    db = SessionLocal()
    try:
        rows = db.query(SpeakerProfile).all()
        return [{"id": r.id, "name": r.name, "n_updates": r.n_updates} for r in rows]
    finally:
        db.close()