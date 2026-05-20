def _start(x):
    return float(x["start"]) if isinstance(x, dict) else float(x.start)

def _end(x):
    return float(x["end"]) if isinstance(x, dict) else float(x.end)

def _text(x):
    return x.get("text", "") if isinstance(x, dict) else getattr(x, "text", "")

def _speaker(x):
    return x.get("speaker") if isinstance(x, dict) else getattr(x, "speaker", None)

def merge(asr_segments, speaker_turns):
    """
    Merge ASR segments with diarization turns.

    Supports:
      - asr_segments as list of dicts OR objects with .start/.end/.text
      - speaker_turns as list of dicts OR objects with .start/.end/.speaker

    Returns:
      List[dict] with keys: start, end, speaker, text
    """
    merged = []

    for seg in asr_segments:
        seg_start = _start(seg)
        seg_end = _end(seg)
        seg_text = _text(seg)

        best_speaker = None
        best_overlap = 0.0

        for t in speaker_turns:
            t_start = _start(t)
            t_end = _end(t)

            overlap = max(0.0, min(seg_end, t_end) - max(seg_start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = _speaker(t)

        merged.append({
            "start": seg_start,
            "end": seg_end,
            "speaker": best_speaker or "UNKNOWN",
            "text": seg_text
        })

    return merged