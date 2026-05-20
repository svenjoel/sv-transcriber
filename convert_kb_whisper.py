from ctranslate2.converters import TransformersConverter

MODEL_ID = "KBLab/kb-whisper-large"

# Choose one:
REVISION = "subtitle"   # ✅ BEST default for your app
# REVISION = "strict"   # more verbatim
# REVISION = None       # fallback

OUTPUT_DIR = "./models/kb-whisper-large-ct2"

converter = TransformersConverter(
    MODEL_ID,
    revision=REVISION,
    copy_files=["tokenizer.json", "preprocessor_config.json"],
)

converter.convert(
    OUTPUT_DIR,
    quantization="float16",
    force=True,
)

print(f"✅ Model converted to: {OUTPUT_DIR}")