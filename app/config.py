import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    app_name: str = os.getenv("APP_NAME", "DriveDB")
    app_env: str = os.getenv("APP_ENV", "development")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-only-change-me")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"

settings = Settings()
