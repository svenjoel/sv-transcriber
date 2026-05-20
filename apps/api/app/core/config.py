import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN", "")
DATA_DIR = os.getenv("DATA_DIR", "../../data")
DB_URL = os.getenv("DB_URL", "sqlite:///../../data/db/app.db")
