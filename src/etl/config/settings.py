import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    # BigQuery / GCP Configuration
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "cloud-data-project")
    DATASET_ID = os.getenv("DATASET_ID", "thelook_dwh")
    
    # GCS Configuration
    GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "etl-staging-0")
    GCS_STAGING_PATH = os.getenv("GCS_STAGING_PATH", "raw")

    # Local Paths
    # Assumes project structure like: root/src/etl/config/settings.py
    # data/ is at: root/data/
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    LOCAL_DATA_DIR = BASE_DIR / "data"
    LOCAL_DWH_DIR = BASE_DIR / "dwh"

settings = Settings()
