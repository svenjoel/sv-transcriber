from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import tempfile
import os

app = FastAPI()

print("🔥 Loading KB Whisper model on GPU...")

model = WhisperModel(
    "jestillore/kb-whisper-large-ct2",
    device="cuda",
    compute_type="float16"
)

print("✅ Model loaded successfully!")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1] or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language="sv",        # force Swedish
            task="transcribe",
            beam_size=5,          # accuracy/speed balance
            vad_filter=True       # ✅ big improvement for real conversations
        )

        result = [
            {
                "start": float(s.start),
                "end": float(s.end),
                "text": s.text.strip()
            }
            for s in segments
        ]

        return result

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)