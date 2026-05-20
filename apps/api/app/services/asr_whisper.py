import requests
from pathlib import Path
from typing import List, Dict, Any

ASR_URL = "http://127.0.0.1:8010/transcribe"

def transcribe_sv(wav_path: Path) -> List[Dict[str, Any]]:
    with open(wav_path, "rb") as f:
        response = requests.post(
            ASR_URL,
            files={"file": (wav_path.name, f)}
        )

    response.raise_for_status()
    return response.json()