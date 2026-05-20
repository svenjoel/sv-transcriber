from dataclasses import dataclass
from pathlib import Path
from typing import List
import os
import torch
import inspect

from pyannote.audio import Pipeline

@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str

_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    hf_token = os.getenv("HF_TOKEN", "").strip()

    # If you have logged in via huggingface-cli, you can use True.
    # Otherwise we require HF_TOKEN to be set to the actual "hf_..." token string.
    auth_value = hf_token if hf_token else True

    # ✅ pyannote.audio 3.1-compatible diarization pipeline
    model_id = "pyannote/speaker-diarization-3.1"

    # Choose correct kwarg name depending on installed pyannote.audio
    sig = inspect.signature(Pipeline.from_pretrained)
    kwargs = {}
    if "token" in sig.parameters:
        kwargs["token"] = auth_value
    else:
        kwargs["use_auth_token"] = auth_value

    _pipeline = Pipeline.from_pretrained(model_id, **kwargs)

    if _pipeline is None:
        # Most often: gated model not accepted or token not applied.
        raise RuntimeError(
            f"Could not download '{model_id}'. "
            f"Make sure you've accepted the model conditions on Hugging Face and that HF_TOKEN is valid."
        )

    # Force CPU (avoids CUDA compatibility issues)
    _pipeline.to(torch.device("cpu"))

    return _pipeline

def diarize(audio_wav: Path) -> List[SpeakerTurn]:
    pipeline = get_pipeline()
    output = pipeline(str(audio_wav))

    turns: List[SpeakerTurn] = []
    for turn, _, speaker in output.itertracks(yield_label=True):
        turns.append(SpeakerTurn(start=float(turn.start), end=float(turn.end), speaker=str(speaker)))
    return turns