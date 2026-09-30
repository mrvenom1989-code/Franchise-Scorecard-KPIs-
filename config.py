import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Explicitly load .env from the same directory as config.py
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://amjzomlovbuwjneqnumv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "scorecard_dev_secret_key_2026_xyz")

# Service-role client for backend operations
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[ERROR] Failed to initialize Supabase client: {e}")
