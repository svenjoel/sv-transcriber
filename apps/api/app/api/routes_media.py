import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import DATA_DIR
from app.db.session import SessionLocal, init_db
from app.db.models import Media, Transcript, SpeakerProfile

from app.services.speaker_memory import embed_speakers, match_speakers_with_meta, upsert_profile

router = APIRouter()

AUTO_MATCH_THRESHOLD = 0.40        # candidate match threshold
AUTO_ACCEPT_SIM = 0.90             # auto-accept only above this


CHUNK_SIZE = 1024 * 64


def _apply_speaker_maps(artifact: Dict[str, Any]) -> None:
    segments = artifact.get("segments") or []
    manual = artifact.get("speaker_map") or {}
    auto_accepted = artifact.get("speaker_map_auto_accepted") or {}
    auto_meta = artifact.get("speaker_map_auto_meta") or {}

    for seg in segments:
        original = seg.get("original_speaker") or seg.get("speaker")
        if not original:
            continue

        # always preserve diarization label for stable lookups
        seg["original_speaker"] = original

        # naming priority: manual > auto-accepted
        if original in manual and manual[original]:
            seg["speaker"] = manual[original]
        elif original in auto_accepted and auto_accepted[original]:
            seg["speaker"] = auto_accepted[original]

        # attach confidence/similarity per segment (clean UI contract)
        meta = auto_meta.get(original)
        if meta:
            seg["confidence"] = meta.get("confidence")
            seg["similarity"] = meta.get("similarity")
        else:
            seg["confidence"] = None
            seg["similarity"] = None


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    init_db()

    media_dir = Path(DATA_DIR) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    dest = media_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    db = SessionLocal()
    try:
        m = Media(filename=file.filename, path=str(dest))
        db.add(m)
        db.commit()
        db.refresh(m)

        from app.workers.pipeline import run_pipeline
        run_dir = Path(DATA_DIR) / "runs" / str(m.id)
        artifact = run_pipeline(Path(dest), run_dir, lambda *args: None)

        speaker_map_auto = {}
        speaker_map_auto_meta = {}
        speaker_map_auto_accepted = {}
        auto_reason = ""

        try:
            profiles_count = db.query(SpeakerProfile).count()
            if profiles_count == 0:
                auto_reason = "no_profiles_enrolled"
            else:
                wav_path = artifact.get("wav_path")
                speaker_turns = artifact.get("speaker_turns", [])

                if wav_path and speaker_turns:
                    spk_embs = embed_speakers(wav_path, speaker_turns)
                    if not spk_embs:
                        auto_reason = "no_embeddings"
                    else:
                        speaker_map_auto, speaker_map_auto_meta = match_speakers_with_meta(
                            db, spk_embs, threshold=AUTO_MATCH_THRESHOLD
                        )

                        for label, info in (speaker_map_auto_meta or {}).items():
                            best_name = info.get("best_name")
                            sim = info.get("similarity")
                            matched = info.get("matched", False)
                            if matched and best_name and isinstance(sim, (int, float)) and sim >= AUTO_ACCEPT_SIM:
                                speaker_map_auto_accepted[label] = best_name

                        if not speaker_map_auto:
                            auto_reason = "no_match_above_threshold"
                        elif not speaker_map_auto_accepted:
                            auto_reason = "matches_found_but_none_auto_accepted"
                else:
                    auto_reason = "missing_inputs"

        except Exception as e:
            auto_reason = "auto_match_error"
            print("⚠️ auto-match error:", e)

        artifact["speaker_map_auto"] = speaker_map_auto
        artifact["speaker_map_auto_meta"] = speaker_map_auto_meta
        artifact["speaker_map_auto_accepted"] = speaker_map_auto_accepted
        artifact["speaker_map_auto_accept_threshold"] = AUTO_ACCEPT_SIM
        artifact["speaker_map_auto_reason"] = auto_reason

        _apply_speaker_maps(artifact)

        t = Transcript(
            id=artifact["transcript_id"],
            media_id=m.id,
            language=artifact.get("language", "sv"),
            json_blob=json.dumps(artifact),
        )
        db.add(t)
        db.commit()

        m.transcript = artifact.get("full_text")
        db.commit()
        db.refresh(m)

        return {
            "id": m.id,
            "filename": m.filename,
            "status": "done",
            "speaker_map_auto": speaker_map_auto,
            "speaker_map_auto_meta": speaker_map_auto_meta,
            "speaker_map_auto_reason": auto_reason,
        }

    finally:
        db.close()


@router.get("/{media_id}")
def get_media(media_id: int):
    init_db()
    db = SessionLocal()
    try:
        m = db.query(Media).filter(Media.id == media_id).first()
        if not m:
            return {"error": "not found"}

        t = db.query(Transcript).filter(Transcript.media_id == media_id).first()

        if not t:
            return {"id": m.id, "filename": m.filename, "status": "uploaded"}

        artifact = json.loads(t.json_blob)

        artifact.setdefault("speaker_map", {})
        artifact.setdefault("speaker_map_auto", {})
        artifact.setdefault("speaker_map_auto_meta", {})
        artifact.setdefault("speaker_map_auto_accepted", {})
        artifact.setdefault("speaker_map_auto_accept_threshold", AUTO_ACCEPT_SIM)
        artifact.setdefault("speaker_map_auto_reason", "")

        _apply_speaker_maps(artifact)

        return {
            "id": m.id,
            "filename": m.filename,
            "status": "done",
            "full_text": artifact.get("full_text") or m.transcript,
            "segments": artifact.get("segments"),
            "speakers": artifact.get("speakers"),
            "speaker_map": artifact.get("speaker_map"),
            "speaker_map_auto": artifact.get("speaker_map_auto"),
            "speaker_map_auto_meta": artifact.get("speaker_map_auto_meta"),
            "speaker_map_auto_accepted": artifact.get("speaker_map_auto_accepted"),
            "speaker_map_auto_accept_threshold": artifact.get("speaker_map_auto_accept_threshold"),
            "speaker_map_auto_reason": artifact.get("speaker_map_auto_reason"),
        }

    finally:
        db.close()

@router.get("/{media_id}/audio")
def get_media_audio(media_id: int, request: Request):
    init_db()
    db = SessionLocal()
    try:
        t = db.query(Transcript).filter(Transcript.media_id == media_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="no transcript found")

        artifact = json.loads(t.json_blob)
        wav_path = artifact.get("wav_path")
        if not wav_path or not Path(wav_path).exists():
            raise HTTPException(status_code=404, detail="audio not found")

        file_size = os.path.getsize(wav_path)
        range_header = request.headers.get("range")

        if range_header:
            # ✅ parse "bytes=start-end"
            bytes_range = range_header.replace("bytes=", "").split("-")
            start = int(bytes_range[0])
            end = int(bytes_range[1]) if bytes_range[1] else file_size - 1

            def iter_file():
                with open(wav_path, "rb") as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = f.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)

            return StreamingResponse(
                iter_file(),
                status_code=206,
                media_type="audio/wav",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1),
                },
            )

        # ✅ fallback (initial load)
        return StreamingResponse(
            open(wav_path, "rb"),
            media_type="audio/wav",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    finally:
        db.close()

@router.post("/{media_id}/speaker-map")
def save_speaker_map(media_id: int, mapping: dict = Body(...)):
    init_db()
    db = SessionLocal()
    try:
        t = db.query(Transcript).filter(Transcript.media_id == media_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="no transcript found for this media_id")

        artifact = json.loads(t.json_blob)
        artifact["speaker_map"] = mapping

        enrolled = []
        debug = {"embedding_keys": [], "mapping_keys": list(mapping.keys())}

        try:
            wav_path = artifact.get("wav_path")
            speaker_turns = artifact.get("speaker_turns", [])
            if wav_path and speaker_turns:
                spk_embs = embed_speakers(wav_path, speaker_turns) or {}
                debug["embedding_keys"] = list(spk_embs.keys())

                only_embedding = next(iter(spk_embs.values())) if len(spk_embs) == 1 else None

                for diar_label, name in mapping.items():
                    name = (name or "").strip()
                    if not name:
                        continue

                    if diar_label in spk_embs:
                        emb = spk_embs[diar_label]
                    elif only_embedding is not None:
                        emb = only_embedding
                    else:
                        emb = next(iter(spk_embs.values()))

                    upsert_profile(db, name, emb)
                    enrolled.append(name)

        except Exception as e:
            print("⚠️ Enrollment error:", e)

        _apply_speaker_maps(artifact)
        artifact["speaker_enrollment_debug"] = debug
        t.json_blob = json.dumps(artifact)
        db.commit()

        return {"status": "ok", "speaker_map": artifact.get("speaker_map", {}), "enrolled": enrolled, "debug": debug}

    finally:
        db.close()