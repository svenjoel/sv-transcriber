from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")

def transcribe_audio(file_path):
    segments, info = model.transcribe(file_path)

    text = ""
    for segment in segments:
        text += segment.text + " "

    return text.strip()