import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.0.100:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llama3.2:3b")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "apia"),
    "charset": "utf8mb4",
    "autocommit": True,
}

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "changeme-admin-2024")
