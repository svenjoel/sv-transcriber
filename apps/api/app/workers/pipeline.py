from uuid import uuid4
from pathlib import Path
from collections import defaultdict

from app.services.ffmpeg import to_wav_16k_mono
from app.services.asr_whisper import transcribe_sv
from app.services.diarization_pyannote import diarize
from app.services.merge_segments import merge

def smooth_speakers(segments, min_confidence=80):
    """
    Simple smoothing:
    - If a segment has low confidence, inherit previous speaker
    - Keeps conversation stable
    """
    prev_speaker = None

    for seg in segments:
        conf = seg.get("confidence")

        if conf is not None and conf < min_confidence and prev_speaker:
            seg["speaker"] = prev_speaker

        prev_speaker = seg["speaker"]

    return segments

def run_pipeline(input_media: Path, run_dir: Path, update_cb):
    run_dir.mkdir(parents=True, exist_ok=True)

    update_cb("running", 0.10, "ffmpeg normalize")
    wav = to_wav_16k_mono(input_media, run_dir / "audio.wav")

    update_cb("running", 0.45, "transcribing (sv)")
    asr_segments = transcribe_sv(wav)

    update_cb("running", 0.80, "diarizing speakers")

    try:
        speaker_turns_raw = diarize(wav)
    except Exception as e:
        print("Diarization failed (continuing without speakers):", e)
        speaker_turns_raw = []


    # ✅ IMPORTANT: normalize speaker_turns into dicts
    speaker_turns = []
    for t in speaker_turns_raw:
        if hasattr(t, "start"):  # pyannote object
            speaker_turns.append({
                "start": float(t.start),
                "end": float(t.end),
                "speaker": str(t.speaker)
            })
        else:
            speaker_turns.append(t)

    update_cb("running", 0.92, "merging transcript + speakers")
    merged = merge(asr_segments, speaker_turns)

    # ✅ Detect unique speakers BEFORE collapse
    unique_speakers = set(seg.get("speaker") for seg in merged if seg.get("speaker"))

    # ✅ Collapse to single speaker if needed

    if len(unique_speakers) == 1:
        for seg in merged:
            seg["original_speaker"] = seg.get("speaker")   # ✅ save original FIRST
            seg["speaker"] = "Speaker"

        for t in speaker_turns:
            t["speaker"] = "Speaker"


        # ✅ CRITICAL: ALSO collapse speaker_turns
        for t in speaker_turns:
            t["speaker"] = "Speaker"

    # ✅ Merge consecutive segments with same speaker
    merged_clean = []
    for seg in merged:
        if not merged_clean:
            merged_clean.append(seg)
            continue

        prev = merged_clean[-1]

        if prev["speaker"] == seg["speaker"]:
            prev["text"] += " " + seg["text"]
            prev["end"] = seg.get("end", prev["end"])
        else:
            merged_clean.append(seg)

    merged = merged_clean
    merged = smooth_speakers(merged)

    # ✅ Build full transcript
    full_text = " ".join(seg["text"] for seg in merged if seg.get("text"))

    # ✅ Group by speaker
    speaker_map = defaultdict(list)

    for seg in merged:
        speaker = seg.get("speaker", "UNKNOWN")
        speaker_map[speaker].append(seg["text"])

    # ✅ Create speaker summaries
    speakers = []
    for speaker, texts in speaker_map.items():
        speakers.append({
            "speaker": speaker,
            "text": " ".join(texts),
            "num_segments": len(texts)
        })

    transcript_id = uuid4().hex

    return {
        "transcript_id": transcript_id,
        "language": "sv",
        "media_filename": input_media.name,

        # ✅ CRITICAL for speaker memory
        "wav_path": str(Path(wav).resolve()),
        "speaker_turns": speaker_turns,

        "segments": merged,
        "full_text": full_text,
        "speakers": speakers
    }