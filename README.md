# sv-transcriber (upload → Swedish transcription → diarization → interactive editor)

This repo is a **local-first** web app: upload Swedish audio/video, transcribe it, diarize speakers, and edit/rename speakers in an interactive UI.

It follows a proven pattern: **FastAPI backend + web GUI**, and uses `pyannote.audio` Community-1 for diarization.

## What you get (MVP)
- Upload audio/video (mp3, wav, m4a, mp4…)
- FFmpeg normalizes to mono 16kHz WAV
- Transcription (default: `faster-whisper`) with `language=sv`
- Speaker diarization with **pyannote Community-1**
- Merge → speaker-attributed transcript segments
- Web UI: upload, job progress, transcript viewer, speaker rename

> Speaker “learning” (voiceprints) is scaffolded as an extension point, but is **not enabled** in this MVP.

---

## Prerequisites
### Backend
- Python 3.10+ (3.11 works)
- FFmpeg installed and available on PATH
- NVIDIA GPU optional
- Hugging Face token for pyannote Community-1 (gated)

### Frontend
- Node 18+ (or 20)

---

## Quickstart (local dev)

### 1) Backend
```bash
cd apps/api
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set HF_TOKEN

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check: http://localhost:8000/health

### 2) Frontend
```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

Open: http://localhost:3000

---

## Environment variables
Backend (`apps/api/.env`):
- `HF_TOKEN` – Hugging Face access token (required for pyannote Community-1)
- `DATA_DIR` – defaults to `../../data`
- `DB_URL` – defaults to `sqlite:///../../data/db/app.db`

Frontend (`apps/web/.env.local`):
- `NEXT_PUBLIC_API_BASE` – defaults to `http://localhost:8000`

---

## API endpoints (MVP)
- `POST /media/upload` → upload file
- `POST /jobs` → start processing a media_id
- `GET /jobs/{job_id}` → job status/progress
- `GET /transcripts/{transcript_id}` → transcript JSON
- `PUT /transcripts/{transcript_id}/rename-speaker?speaker=SPEAKER_00&name=Joel` → rename a speaker label

---

## Notes
- pyannote models are gated. You must accept conditions on the model page and use a token.
- diarization quality varies with noise/overlap. The UI is meant for quick correction.
