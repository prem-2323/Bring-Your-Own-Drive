import os
import sys

# Ensure project root is in sys.path for Vercel Serverless Functions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app  # noqa: E402
