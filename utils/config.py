# utils/config.py
import os
from dotenv import load_dotenv

load_dotenv()

FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
DIRECTUS_URL = os.getenv("DIRECTUS_URL")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
ORDER_EXPIRE_SECONDS = int(os.getenv("ORDER_EXPIRE_SECONDS", 900))  # default 15 phút
CORS_ORIGINS = os.getenv("CORS_ORIGINS")
PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY")
IMG_EMAIL_URL = os.getenv("IMG_EMAIL_URL", "")

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "In-đỉ In-đi")
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN")