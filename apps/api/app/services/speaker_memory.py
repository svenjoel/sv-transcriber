import os
import json
from typing import Dict, List, Tuple
from pathlib import Path

import numpy as np
import torch
from pyannote.audio import Model, Inference

from app.db.models import SpeakerProfile

SPEAKER_MEMORY_VERSION = "2026-05-18-embed-fallback-v2"

# Matching / learning defaults (can be overridden via env)
DEFAULT_MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.75"))
AUTO_LEARN_ENABLED = os.getenv("SPEAKER_AUTO_LEARN", "1") == "1"
AUTO_LEARN_THRESHOLD = float(os.getenv("SPEAKER_AUTO_LEARN_THRESHOLD", "0.85"))
AUTO_LEARN_MAX = float(os.getenv("SPEAKER_AUTO_LEARN_MAX", "0.98"))  # avoid redundant re-learns

DEBUG_MATCH = os.getenv("SPEAKER_MATCH_DEBUG", "0") == "1"

_inference = None
_sliding_cache: Dict[Tuple[float, float], Inference] = {}


# -------------------------
# Helpers
# -------------------------
def _norm(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-9)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).reshape(-1)
    b = b.astype(np.float32).reshape(-1)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


# -------------------------
# Inference (ALWAYS CPU)
# -------------------------
def get_inference():
    """
    Loads pyannote/embedding once and returns an Inference wrapper.
    We force CPU here to avoid CUDA architecture mismatch issues in your API venv.
    """
    global _inference
    if _inference is not None:
        return _inference

    token = os.getenv("HF_TOKEN", None)
    if not token:
        raise RuntimeError("HF_TOKEN is not set (required for pyannote/embedding).")

    # Some versions accept use_auth_token, newer ones accept token. Try both.
    try:
        model = Model.from_pretrained("pyannote/embedding", use_auth_token=token)
    except TypeError:
        model = Model.from_pretrained("pyannote/embedding", token=token)

    _inference = Inference(model, window="whole")

    # Force CPU unconditionally (safe + avoids RTX 5070 Ti / torch CUDA kernel issues)
    try:
        _inference.to(torch.device("cpu"))
    except Exception:
        pass

    print(f"[speaker_memory] loaded inference ({SPEAKER_MEMORY_VERSION})")
    return _inference


def _get_sliding_inference(duration: float = 3.0, step: float = 1.0) -> Inference:
    """
    Create/reuse an Inference wrapper in sliding-window mode.
    """
    key = (float(duration), float(step))
    if key in _sliding_cache:
        return _sliding_cache[key]

    whole_inf = get_inference()
    model = whole_inf.model  # reuse already-loaded model

    sliding_inf = Inference(model, window="sliding", duration=duration, step=step)

    # Force CPU to match whole inference
    try:
        sliding_inf.to(torch.device("cpu"))
    except Exception:
        pass

    _sliding_cache[key] = sliding_inf
    return sliding_inf


def _embed_whole_file(wav_path: str) -> np.ndarray:
    """
    Whole-file embedding fallback (1 x D) -> normalized (D,)
    """
    inf = get_inference()
    p = str(Path(wav_path).resolve())
    emb = inf(p)  # expected shape (1, D)
    emb = np.asarray(emb).reshape(-1)
    return _norm(emb)


# -------------------------
# Embedding extraction
# -------------------------
def embed_speakers(
    wav_path: str,
    speaker_turns: List[Dict],
    window_duration: float = 3.0,
    window_step: float = 1.0,
    min_overlap_ratio: float = 0.50,
    min_windows_per_speaker: int = 1,
) -> Dict[str, np.ndarray]:
    """
    Multi-speaker embedding extraction.

    Approach:
      1) Sliding embeddings across the file
      2) Assign each window embedding to diarization label with max overlap
      3) Average embeddings per speaker label
      4) Normalize final embedding vectors (important for stable cosine matching)
    """
    wav_path = str(Path(wav_path).resolve())

    # If no turns, fallback to whole-file
    if not speaker_turns:
        return {"Speaker": _embed_whole_file(wav_path)}

    labels = sorted({t.get("speaker") for t in speaker_turns if t.get("speaker")})
    if len(labels) == 0:
        return {"Speaker": _embed_whole_file(wav_path)}

    # Single speaker: whole-file embedding is stable for enrollment
    if len(labels) == 1:
        return {labels[0]: _embed_whole_file(wav_path)}

    sliding_inf = _get_sliding_inference(duration=window_duration, step=window_step)
    embeddings = sliding_inf(wav_path)  # SlidingWindowFeature

    sw = embeddings.sliding_window
    duration = float(sw.duration)
    step = float(sw.step)
    start0 = float(sw.start)

    buckets: Dict[str, List[np.ndarray]] = {lab: [] for lab in labels}
    min_overlap_seconds = duration * float(min_overlap_ratio)

    for i in range(len(embeddings)):
        w_start = start0 + i * step
        w_end = w_start + duration

        best_lab = None
        best_ov = 0.0

        for t in speaker_turns:
            lab = t.get("speaker")
            if not lab:
                continue
            ov = _overlap(w_start, w_end, float(t["start"]), float(t["end"]))
            if ov > best_ov:
                best_ov = ov
                best_lab = lab

        if best_lab is None or best_ov < min_overlap_seconds:
            continue

        vec = np.asarray(embeddings[i]).reshape(-1)
        buckets[best_lab].append(vec)

    out: Dict[str, np.ndarray] = {}
    for lab, vecs in buckets.items():
        if len(vecs) >= int(min_windows_per_speaker):
            vec = np.mean(np.stack(vecs, axis=0), axis=0)
            out[lab] = _norm(vec)

    if not out:
        return {"Speaker": _embed_whole_file(wav_path)}

    return out


# -------------------------
# Profiles (DB)
# -------------------------
def load_profiles(db) -> List[Tuple[int, str, np.ndarray, int]]:
    """
    Loads profiles. Each profile stores a single averaged embedding vector in embedding_json.
    """
    profiles = db.query(SpeakerProfile).all()
    result = []
    for p in profiles:
        vec = np.array(json.loads(p.embedding_json), dtype=np.float32).reshape(-1)
        vec = _norm(vec)
        result.append((p.id, p.name, vec, p.n_updates))
    return result


def upsert_profile(db, name: str, new_embedding: np.ndarray):
    """
    Update profile with running average of embeddings.
    Normalizes before saving for stable cosine matching.
    """
    existing = db.query(SpeakerProfile).filter(SpeakerProfile.name == name).first()
    new_vec = _norm(new_embedding.astype(np.float32).reshape(-1))

    if existing:
        old_vec = np.array(json.loads(existing.embedding_json), dtype=np.float32).reshape(-1)
        old_vec = _norm(old_vec)

        n = int(existing.n_updates)
        updated = (old_vec * n + new_vec) / (n + 1)
        updated = _norm(updated)

        existing.embedding_json = json.dumps(updated.tolist())
        existing.n_updates = n + 1
        db.commit()
        return existing

    p = SpeakerProfile(
        name=name,
        embedding_json=json.dumps(new_vec.tolist()),
        n_updates=1
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# -------------------------
# Matching
# -------------------------
def match_speakers(db, speaker_embeddings: Dict[str, np.ndarray], threshold: float = DEFAULT_MATCH_THRESHOLD) -> Dict[str, str]:
    profiles = load_profiles(db)
    if not profiles:
        return {}

    mapping: Dict[str, str] = {}
    for label, emb in speaker_embeddings.items():
        best_name = None
        best_sim = -1.0

        if DEBUG_MATCH:
            print(f"\n--- Matching speaker: {label} ---")

        for _, name, prof_emb, _ in profiles:
            sim = cosine_similarity(emb, prof_emb)
            if DEBUG_MATCH:
                print(f"   vs {name}: similarity = {sim:.3f}")
            if sim > best_sim:
                best_sim = sim
                best_name = name

        if DEBUG_MATCH:
            print(f"   ✅ best match: {best_name} ({best_sim:.3f})")

        if best_name is not None and best_sim >= threshold:
            mapping[label] = best_name

    return mapping


def match_speakers_with_meta(db, speaker_embeddings: Dict[str, np.ndarray], threshold: float = DEFAULT_MATCH_THRESHOLD):
    """
    Returns:
      mapping: { diar_label: best_name } for matches >= threshold
      meta:    { diar_label: { best_name, similarity, confidence, matched, threshold } }
    """
    profiles = load_profiles(db)
    mapping: Dict[str, str] = {}
    meta: Dict[str, dict] = {}

    if not profiles:
        for label in speaker_embeddings.keys():
            meta[label] = {
                "best_name": None,
                "similarity": None,
                "confidence": None,
                "matched": False,
                "threshold": threshold,
                "reason": "no_profiles"
            }
        return mapping, meta

    for label, emb in speaker_embeddings.items():
        best_name = None
        best_sim = -1.0

        for _, name, prof_emb, _ in profiles:
            sim = cosine_similarity(emb, prof_emb)
            if sim > best_sim:
                best_sim = sim
                best_name = name

        matched = (best_name is not None) and (best_sim >= threshold)
        conf = int(best_sim * 100)

        if matched:
            mapping[label] = best_name

        meta[label] = {
            "best_name": best_name,
            "similarity": float(best_sim),
            "confidence": conf,
            "matched": matched,
            "threshold": threshold,
            "reason": "matched" if matched else "below_threshold",
        }

        # -------------------------
        # Auto-learning (safe-guarded)
        # -------------------------
        if AUTO_LEARN_ENABLED and matched and (AUTO_LEARN_THRESHOLD <= best_sim <= AUTO_LEARN_MAX):
            try:
                upsert_profile(db, best_name, emb)
                if DEBUG_MATCH:
                    print(f"🧠 auto-learned: {best_name} ({best_sim:.3f})")
            except Exception as e:
                print("⚠️ auto-learn failed:", e)

    return mapping, meta