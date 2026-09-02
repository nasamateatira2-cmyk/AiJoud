import os
import asyncio
import threading
from io import BytesIO
from PIL import Image
from flask import Flask
from google import genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# خادم ويب لإبقاء الخدمة نشطة على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud is Live!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# المفاتيح
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# إعداد العميل
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# النموذج المطلوب من جوجل
TARGET_MODEL = "gemini-3.6-flash"

async def generate_with_retry(contents, retries=3):
    """إعادة المحاولة تلقائياً في حال وجود ضغط مؤقت 503"""
    for attempt in range(retries):
        try:
            response = await ai_client.aio.models.generate_content(
                model=TARGET_MODEL,
                contents=contents,
            )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < retries - 1:
                await asyncio.sleep(2) # انتظار ثانيتين وإعادة المحاولة
                continue
            raise e

# رسالة البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud \n"
        "الاحدث والمبني على احدث انظمة الذكاء الصناعي العالمي.\n\n"
        "💡 أرسل سؤالك، أو أي صورة لتحليلها مباشرة!"
    )
    await update.message.reply_text(welcome_text)

# معالجة النصوص
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply = await generate_with_retry(user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"تنبيه من الخادم: {e}")
        print(f"Error text: {e}")

# معالجة الصور
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح هذه الصورة بالتفصيل"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(BytesIO(photo_bytes))

        reply = await generate_with_retry([user_caption, image])
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"تنبيه عند تحليل الصورة: {e}")
        print(f"Error photo: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud is active...")
    app.run_polling(drop_pending_updates=True)
