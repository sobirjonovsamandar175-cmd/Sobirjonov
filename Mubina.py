import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

# .env faylini yuklash (localda ishlash uchun)
load_dotenv()

# Environment o'zgaruvchilarini olish
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")

# Qiymat mavjudligini tekshirish
if not STRING_SESSION:
    print("XATOLIK: STRING_SESSION topilmadi yoki bo'sh! Render Environment Variables bo'limini tekshiring.")
    sys.exit(1)

# Ortiqcha bo'sh joylar yoki qo'shtirnoqlarni olib tashlash
STRING_SESSION = STRING_SESSION.strip().strip("'").strip('"')

# API_ID integer tipida bo'lishi shart
try:
    API_ID = int(API_ID)
except (TypeError, ValueError):
    print("XATOLIK: API_ID noto'g'ri kiritilgan!")
    sys.exit(1)

# Clientni ishga tushirish
try:
    telethon_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    print("Telethon mijoz muvaffaqiyatli sozlandi.")
except Exception as e:
    print(f"Sessiyani yuklashda xatolik: {e}")
    sys.exit(1)
