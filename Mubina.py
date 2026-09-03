import os
import logging
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# 1. Environment fayllarini va loglarni sozlash
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. O'zgaruvchilarni e'lon qilish
BOT_TOKEN = os.getenv("BOT_TOKEN", "7266518556:AAGpLmMBkpr7TrhPCWo9pyhfN_licVXZWVU")
API_ID = int(os.getenv("API_ID", 23832062))
API_HASH = os.getenv("API_HASH", "f734fade59b27912a11f0b475a486267")
STRING_SESSION = os.getenv("STRING_SESSION", "")
ADMIN_GROUP = os.getenv("ADMIN_GROUP", "@online_quiz_tests")
ADMINS = os.getenv("ADMINS", "1738809395")

# 3. Telethon mijozini e'lon qilish
telethon_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# 4. Telegram bot komandalari
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot muvaffaqiyatli ishga tushdi!")

# 5. Bot va Telethon'ni ulash (post_init)
async def post_init(application: Application):
    logger.info("⚡ Telethon mijoziga ulanish tekshirilmoqda...")
    if STRING_SESSION:
        await telethon_client.connect()
        if await telethon_client.is_user_authorized():
            logger.info("✅ Telethon userbot muvaffaqiyatli ulandi!")
        else:
            logger.warning("⚠️ Telethon avtorizatsiyadan o'tmagan! STRING_SESSION kodi noto'g'ri bo'lishi mumkin.")
    else:
        logger.warning("⚠️ STRING_SESSION topilmadi. Telethon ishga tushirilmadi.")

async def post_shutdown(application: Application):
    if telethon_client.is_connected():
        await telethon_client.disconnect()
        logger.info("🛑 Telethon client o'chirildi.")

# 6. Asosiy ishga tushirish funksiyasi
def main():
    logger.info("🤖 TELEGRAM BOT ISHGA TUSHMOQDA...")

    bot_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Handlerni qo'shish
    bot_app.add_handler(CommandHandler("start", start_command))

    # Polling yuritish
    bot_app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
