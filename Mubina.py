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

# Logging sozlamasi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Konfiguratsiya va Muhit o'zgaruvchilari (Render Environment Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN", "7266518556:AAFO01XaYg2zM_p10r_x_ODtXCPukQt5QOQ")
API_ID = int(os.getenv("API_ID", "23832062"))
API_HASH = os.getenv("API_HASH", "f734fade59b27912a11f0b475a486267")
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "")  # Render qayta yonishida session o'chib ketmasligi uchun

# SMS/Humo xabarlarini yuboradigan bot yoki kanal username/ID si
HUMO_BOT_ID = os.getenv("HUMO_BOT_ID", "HumoCardBot") 

# To'lov so'rovlarini saqlash uchun lug'at (baza)
pending_payments = {}

# Telethon mijozini ishga tushirish (StringSession orqali)
telethon_client = TelegramClient(StringSession(TELETHON_SESSION), API_ID, API_HASH)

# --- 1. AIOHTTP Keep-Alive Server (Render o'chib qolmasligi uchun) ---
async def handle_ping(request):
    return web.Response(text="Bot is running", status=200)

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

# --- 2. Humo Bot / Bank SMS Xabarlarini O'qish Mantiqi ---
@telethon_client.on(events.NewMessage(chats=HUMO_BOT_ID))
async def humo_message_handler(event):
    text = event.raw_text
    logger.info(f"📩 Humo botdan xabar keldi: {text}")

    # Xabar matnidan barcha raqamlarni ajratib olish (Masalan: "+1 003 so'm" yoki "1003 UZS")
    numbers = re.findall(r'\b\d[\d\s,.]*\b', text)
    
    for num in numbers:
        clean_num = int(re.sub(r'[^\d]', '', num))
        
        # Kutilayotgan to'lovlar ichida aynan shu summa bor-yo'qligini tekshirish
        matched_order_id = None
        for order_id, data in list(pending_payments.items()):
            if data["amount"] == clean_num and data["status"] == "pending":
                matched_order_id = order_id
                break
        
        # Agar mos to'lov topilsa:
        if matched_order_id:
            pending_payments[matched_order_id]["status"] = "paid"
            user_id = pending_payments[matched_order_id]["user_id"]
            
            # Bot orqali foydalanuvchiga muvaffaqiyatli to'lov haqida bildirishnoma yuborish
            bot_app = getattr(telethon_client, 'bot_app', None)
            if bot_app:
                await bot_app.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ **To'lov muvaffaqiyatli qabul qilindi!**\n\n"
                         f"🏷 Buyurtma kodi: `{matched_order_id}`\n"
                         f"💰 Qabul qilingan summa: **{clean_num:,} so'm**".replace(",", " "),
                    parse_mode="Markdown"
                )
            logger.info(f"🎉 Auto-to'lov tasdiqlandi: Order {matched_order_id}, Summa: {clean_num}")
            break

# --- 3. Telegram Bot Handlers (Buyruqlar va Tugmalar) ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xush kelibsiz! To'lov so'rovini yaratish uchun summani kiriting (Masalan: 1000)."
    )

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        return

    base_amount = int(text)
    
    # Har bir buyurtma uchun unikal tiyin/summa qo'shish (masalan: 1000 -> 1003)
    extra = (len(pending_payments) + 3) % 99 + 1
    exact_amount = base_amount + extra
    
    # Unikal buyurtma kodi
    order_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    # Bazaga saqlash
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
        f"⚠️ **Eslatma:** Kartaga **aynan {exact_amount:,} so'm** o'tkazishingiz kerak. "
        f"Boshqa summa o'tkazilsa avtomatik moslashtirilmaydi.\n\n"
        f"⚠️ **Kutilish muddati:** 5 daqiqa"
    ).replace(",", " ")

    await update.message.reply_text(
        msg_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

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
            await query.answer(
                "⏳ To'lov hali kelib tushmadi. O'tkazmani bajargan bo'lsangiz, 10-15 soniya kutib qayta bosing.",
                show_alert=True
            )

    elif data.startswith("cancel_"):
        order_id = data.replace("cancel_", "")
        if order_id in pending_payments:
            del pending_payments[order_id]
        await query.answer("Bekor qilindi")
        await query.edit_message_text("❌ To'lov so'rovi bekor qilindi.")

# --- 4. Asosiy Ishga Tushirish Qismi ---
async def main():
    # Keep-alive serverni ishga tushirish
    await start_web_server()

    # Telegram Bot qurish
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Telethon bilan ulash
    telethon_client.bot_app = app
    await telethon_client.start()

    # Agar session yangi bo'lsa, logga chiqarish
    session_str = telethon_client.session.save()
    logger.info(f"🔑 TELETHON SESSION STRING: {session_str}")

    # Botni ishga tushirish
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("🤖 Bot va Telethon muvaffaqiyatli ishga tushdi!")
    
    # Doimiy ishlash rejimida ushlab turish
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
