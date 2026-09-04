import asyncio
import os
import re
import logging
import string
import random
from datetime import datetime
from aiohttp import web

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# Logging sozlamasi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment Variables (Render Sozlamalari)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "1234567"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "").strip()
HUMO_BOT_ID = os.getenv("HUMO_BOT_ID", "HumoCardBot")  # Humo yoki SMS botingiz ID/Username si
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # O'zingizning Telegram ID ingiz (Ixtiyoriy)

# Global xotira
pending_payments = {}
login_states = {}

# Session obyektini xavfsiz yaratish
session_obj = StringSession(TELETHON_SESSION) if TELETHON_SESSION else StringSession()
telethon_client = TelegramClient(session_obj, API_ID, API_HASH)

# --- 1. AIOHTTP Keep-Alive Web Server ---
async def handle_ping(request):
    return web.Response(text="Bot runs smoothly", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_head('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Keep-alive server {port}-portda ishga tushdi!")

# --- 2. Humo Bot / SMS Xabarlarini Avto-O'qish ---
@telethon_client.on(events.NewMessage(chats=HUMO_BOT_ID))
async def humo_message_handler(event):
    text = event.raw_text
    logger.info(f"📩 Humo botdan xabar keldi: {text}")

    # Xabar matnidan summalarni ajratib olish
    numbers = re.findall(r'\b\d[\d\s,.]*\b', text)
    for num in numbers:
        clean_num = int(re.sub(r'[^\d]', '', num))
        
        matched_order = None
        for order_id, data in list(pending_payments.items()):
            if data["amount"] == clean_num and data["status"] == "pending":
                matched_order = order_id
                break
        
        if matched_order:
            pending_payments[matched_order]["status"] = "paid"
            user_id = pending_payments[matched_order]["user_id"]
            
            bot_app = getattr(telethon_client, 'bot_app', None)
            if bot_app:
                await bot_app.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ **To'lov muvaffaqiyatli qabul qilindi!**\n\n"
                         f"🏷 Buyurtma kodi: `{matched_order}`\n"
                         f"💰 Summa: **{clean_num:,} so'm**".replace(",", " "),
                    parse_mode="Markdown"
                )
            logger.info(f"🎉 Auto-to'lov tasdiqlandi: Order {matched_order}, Summa: {clean_num}")
            break

# --- 3. Akkauntni Bot orqali ulash (/connect) ---
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Bu buyruq faqat bot admini uchun!")
        return

    try:
        if await telethon_client.is_user_authorized():
            await update.message.reply_text("✅ Akkaunt allaqachon botga ulangan va faol!")
            return
    except Exception:
        pass

    await update.message.reply_text("📱 Akkaunt telefon raqamini kiriting (Masalan: +998901234567):")
    login_states[update.effective_user.id] = {"step": "phone"}

async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1. Admin ulanish jarayonida bo'lsa
    if user_id in login_states:
        state = login_states[user_id]
        
        if state["step"] == "phone":
            try:
                phone_code_hash = await telethon_client.send_code_request(text)
                state["phone"] = text
                state["hash"] = phone_code_hash.phone_code_hash
                state["step"] = "code"
                await update.message.reply_text("📥 Telegram'ga kelgan SMS/Login kodni kiriting:")
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")
                del login_states[user_id]

        elif state["step"] == "code":
            try:
                await telethon_client.sign_in(
                    phone=state["phone"],
                    code=text,
                    phone_code_hash=state["hash"]
                )
                session_str = telethon_client.session.save()
                await update.message.reply_text(
                    f"🎉 **Akkaunt muvaffaqiyatli ulandi!**\n\n"
                    f"⚠️ Render qayta tushganda ham uzilib qolmasligi uchun ushbu `SESSION` matnidan nusxa oling va Render Dashboard -> Environment variables ga `TELETHON_SESSION` kaliti bilan joylang:\n\n"
                    f"`{session_str}`",
                    parse_mode="Markdown"
                )
                del login_states[user_id]
            except SessionPasswordNeededError:
                state["step"] = "password"
                await update.message.reply_text("🔐 Akkauntingizda 2-bosqichli parol (2FA) mavjud. Parolni kiriting:")
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik: {e}")
                del login_states[user_id]

        elif state["step"] == "password":
            try:
                await telethon_client.sign_in(password=text)
                session_str = telethon_client.session.save()
                await update.message.reply_text(
                    f"🎉 **Akkaunt muvaffaqiyatli ulandi!**\n\n`TELETHON_SESSION` kodingiz:\n`{session_str}`",
                    parse_mode="Markdown"
                )
                del login_states[user_id]
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik: {e}")
                del login_states[user_id]
        return

    # 2. Oddiy foydalanuvchi summa kiritsa (To'lov so'rovi yaratish)
    if text.isdigit():
        base_amount = int(text)
        extra = (len(pending_payments) + 3) % 99 + 1
        exact_amount = base_amount + extra
        order_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

        pending_payments[order_id] = {
            "user_id": update.message.chat_id,
            "amount": exact_amount,
            "status": "pending",
            "created_at": datetime.now()
        }

        keyboard = [
            [InlineKeyboardButton("✅ To'lovni tekshirish", callback_data=f"check_{order_id}")],
            [InlineKeyboardButton("⚠️ Bekor qilish", callback_data=f"cancel_{order_id}")]
        ]
        
        msg_text = (
            f"✅ **To'lov so'rovi yaratildi!**\n\n"
            f"🏷 Buyurtma kodi: `{order_id}`\n"
            f"💰 To'lanadigan ANIQ summa: **{exact_amount:,} so'm**\n\n"
            f"💳 To'lov uchun karta:\n"
            f"`9860190112173652`\n"
            f"👤 Egasi: Sobirjonov Samandar\n\n"
            f"⚠️ **Eslatma:** Kartaga **aynan {exact_amount:,} so'm** o'tkazishingiz kerak.\n\n"
            f"⚠️ **Kutilish muddati:** 5 daqiqa"
        ).replace(",", " ")

        await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- 4. Bot Handler va Tugmalar ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Xush kelibsiz! To'lov so'rovi yaratish uchun summani kiriting (Masalan: 1000).")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("check_"):
        order_id = data.replace("check_", "")
        order = pending_payments.get(order_id)
        
        if not order:
            await query.answer("❌ Buyurtma topilmadi yoki muddati o'tgan.", show_alert=True)
            return
            
        if order["status"] == "paid":
            await query.answer("✅ To'lov tasdiqlangan!", show_alert=True)
            await query.edit_message_text(
                f"🎉 **To'lov muvaffaqiyatli qabul qilindi!**\n\n"
                f"🏷 Buyurtma kodi: `{order_id}`\n"
                f"💰 Summa: **{order['amount']:,} so'm**".replace(",", " "),
                parse_mode="Markdown"
            )
        else:
            await query.answer("⏳ To'lov hali kelib tushmadi. Biroz kutib qayta bosing.", show_alert=True)

    elif data.startswith("cancel_"):
        order_id = data.replace("cancel_", "")
        if order_id in pending_payments:
            del pending_payments[order_id]
        await query.answer("Bekor qilindi")
        await query.edit_message_text("❌ To'lov so'rovi bekor qilindi.")

# --- 5. Main Loop ---
async def main():
    await start_web_server()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    telethon_client.bot_app = app
    await telethon_client.connect()

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("🤖 Bot va Telethon muvaffaqiyatli ishga tushdi!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
