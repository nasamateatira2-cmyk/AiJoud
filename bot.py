import os
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
    return "Ai Joud is Ultra Fast!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# جلب المفاتيح
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# قائمة النماذج حسب الأفضلية لتجاوز ضغط 503 فوراً
MODELS_POOL = [
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash"
]

async def smart_generate(contents):
    """تجربة النماذج بالتتابع وبسرعة فائقة عند انشغال أي منها"""
    last_err = None
    for model_name in MODELS_POOL:
        try:
            response = await ai_client.aio.models.generate_content(
                model=model_name,
                contents=contents,
            )
            if response.text:
                return response.text
        except Exception as e:
            last_err = e
            # إذا كان الخطأ بسبب الضغط (503) أو عدم التوفر، يكمل فوراً للنموذج التالي
            continue
    raise last_err

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
        reply = await smart_generate(user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("الخوادم تشهد ضغطاً استثنائياً، يرجى كتابة السؤال مرة ثانية.")
        print(f"Text Error: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح هذه الصورة بوضوح ودقة"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(BytesIO(photo_bytes))

        reply = await smart_generate([user_caption, image])
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("تعذر تحليل الصورة، أعد المحاولة بعد قليل.")
        print(f"Photo Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud Multi-Engine running...")
    app.run_polling(drop_pending_updates=True)
