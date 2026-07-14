import os


def get_backend_api_url():
    raw_url = (os.getenv("BACKEND_API_URL") or "http://localhost:8000").strip()
    if not raw_url:
        return "http://localhost:8000"

    raw_url = raw_url.rstrip("/")
    if raw_url.lower().endswith("/api"):
        raw_url = raw_url[:-4]

    return raw_url
