import os
import threading
from io import BytesIO
from PIL import Image
from flask import Flask
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# خادم ويب صغير لإبقاء الخطة المجانية على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# جلب المفاتيح من Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# تخزين جلسات المحادثة لكل مستخدم لتذكر السياق
user_chats = {}

def get_or_create_chat(user_id):
    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])
    return user_chats[user_id]

# أمر البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_chats[user_id] = model.start_chat(history=[]) # إعادة ضبط المحادثة
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud \n"
        "الاحدث والمبني على احدث انظمة الذكاء الصناعي العالمي.\n\n"
        "💡 يمكنك إرسال نصوص، أسئلة متتابعة، أو حتى صور لتحليلها!"
    )
    await update.message.reply_text(welcome_text)

# معالجة الرسائل النصية مع حفظ السياق
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    chat_session = get_or_create_chat(user_id)

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = chat_session.send_message(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("حدث خطأ أثناء معالجة الرد، يرجى المحاولة لاحقاً.")
        print(f"Error text: {e}")

# معالجة الصور المرسلة للبوت
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح لي هذه الصورة بالتفصيل"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # تحميل الصورة بأعلى دقة متوفرة
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(BytesIO(photo_bytes))

        # تحليل الصورة عبر Gemini
        response = model.generate_content([user_caption, image])
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("تعذر تحليل الصورة، حاول مرة أخرى.")
        print(f"Error photo: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("البوت المتطور يعمل الآن...")
    app.run_polling()
