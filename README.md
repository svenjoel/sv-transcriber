# sv-transcriber

A modern web app for **transcribing Swedish audio/video**, identifying speakers, and navigating conversations with precision.

Built as a hands-on project exploring:
- local-first AI
- speaker diarization + memory
- transcript UX beyond plain text

This is evolving from a **tool → into a transcript intelligence product**.

---

## ✨ Features

### 🎙️ Transcription
- Upload audio or video files
- Automatic speech-to-text transcription
- Swedish-first (works for other languages too)

---

### 🧑‍🤝‍🧑 Speaker Identification (Diarization + Memory)
- Automatically detects “who spoke when”
- Persistent speaker recognition across recordings
- Confidence scoring per speaker match
- Auto-accept high-confidence matches (configurable)

---

### 💬 Transcript Experience
- Chat-style transcript UI (per speaker)
- Active segment highlighting
- Auto-scroll to current segment
- Inline speaker renaming

---

### 🎧 Audio Playback (Fully Synced)
- Custom audio player (single timeline)
- Click a transcript bubble → jump to exact timestamp
- **Play only that segment** (auto-stop at segment end)
- Smooth and accurate seeking

---

### 🎯 Segment Mode
Clicking a transcript bubble activates:

- 🎧 Playing selection indicator
- Playback is limited to that segment only
- Automatically exits when segment ends

---

### ⌨️ Keyboard Shortcuts

Shortcuts are disabled while typing in inputs (e.g. renaming speakers).

| Action | Shortcut |
|--------|--------|
| Play / Pause | `Space` |
| Skip ±5 seconds | `← / →` |
| Skip ±15 seconds | `Shift + ← / →` |
| Previous / Next segment | `↑ / ↓` |

---

### 🧠 Speaker Manager
- Rename speakers inline
- Accept auto-suggestions
- Clear overrides
- Confidence indicators
- Auto-save on blur

---

## 🏗️ Architecture

### Frontend
- Next.js (App Router)
- React (client components)
- Custom transcript + audio UX

### Backend
- FastAPI
- ffmpeg audio processing pipeline
- matching
- Range-enabled audio streaming (required for seeking)

### 🧠 ASR Service (Local AI Runtime)

The transcription pipeline runs in a **separate Python environment** for better isolation and performance.

This service handles:
- speech-to-text (KB Whisper)
- speaker diarization
- embedding generation for speaker recognition

---

## 🚀 Getting Started

Follow these steps to run the application locally.

---

### 1. Clone the repository

```bash
git clone https://github.com/svenjoel/sv-transcriber.git
cd sv-transcriber
```

### 2. Setup environment variables
Create a backend .env file inside apps/api:
```bash
cp apps/api/.env.sample apps/api/.env
```

Add:
- `HF_TOKEN=hf_your_token_here`

Optinal
- `SPEAKER_MATCH_THRESHOLD=0.75`
- `SPEAKER_AUTO_LEARN=1`
- `SPEAKER_AUTO_LEARN_THRESHOLD=0.85`
- `SPEAKER_AUTO_LEARN_MAX=0.98`
- `SPEAKER_MATCH_DEBUG=0`

### 3. Backend (FastAPI)
```bash
cd apps/api
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend runs on: `http://127.0.0.1:8000`

---



### 4) Setup ASR environment

```bash
cd apps/asr_service
python -m venv asr_venv
source asr_venv/bin/activate     # Windows: asr_venv\Scripts\activate
pip install -r requirements.txt
```

ASR service runs on: `http://127.0.0.1:8001`

### 5. Frontend (Next.js)
```bash
cd apps/web
npm install
npm run dev
```

Frontend runs on: `http://127.0.0.1:8000`

### 6. Open the app

Open `http://localhost:3000`

---
## ⚠️ Important notes
- This environment can use GPU (CUDA) if available
- First startup may download ML models (can take time)
- Uses HF_TOKEN for gated diarization models
- Keep separate from API environment to avoid dependency conflicts

## 🔄 Full system overview
You now run two backend services + one frontend:

| Service        | Port | Responsibility                         |
|----------------|------|----------------------------------------|
| API (FastAPI)  | 8000 | orchestration, storage, endpoints      |
| ASR Service    | 8001 | transcription + diarization            |
| Frontend       | 3000 | UI                                     |



