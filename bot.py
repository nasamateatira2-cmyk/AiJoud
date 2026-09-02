import os
import asyncio
import threading
from io import BytesIO
from PIL import Image
from flask import Flask
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# خادم ويب خفيف لإبقاء السيرفر نشطاً
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud is Awake & Fast!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# المفاتيح
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)
TARGET_MODEL = "gemini-3.6-flash"

# إعدادات لتسريع الاستجابة وتقليل وقت المعالجة
FAST_CONFIG = types.GenerateContentConfig(
    temperature=0.7,
    max_output_tokens=1000, # ردود سريعة وموجزة لتفادي البطء
)

async def generate_fast(contents):
    """توليد سريع مع مهلة زمنية قصيرة"""
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                ai_client.aio.models.generate_content(
                    model=TARGET_MODEL,
                    contents=contents,
                    config=FAST_CONFIG
                ),
                timeout=15.0 # حد أقصى 15 ثانية للطلب
            )
            return response.text
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud \n"
        "الاحدث والمبني على احدث انظمة الذكاء الصناعي العالمي.\n\n"
        "💡 أرسل سؤالك، أو أي صورة لتحليلها مباشرة!"
    )
    await update.message.reply_text(welcome_text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply = await generate_fast(user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("عذراً، يرجى تكرار السؤال ثانية.")
        print(f"Error: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح هذه الصورة باختصار ووضوح"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(BytesIO(photo_bytes))

        reply = await generate_fast([user_caption, image])
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("تعذر تحليل الصورة، حاول مرة أخرى.")
        print(f"Error photo: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud is active & fast...")
    app.run_polling(drop_pending_updates=True)
