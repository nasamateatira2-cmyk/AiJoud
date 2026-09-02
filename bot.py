import os
import threading
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

# خادم ويب صغير لتفعيل الخطة المجانية على Render
web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is running perfectly!"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)


# جلب المفاتيح من Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# رسالة الترحيب
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud "
        "الاحدث والمبني على احدث انظمة الذكاء الصناعي العالمي"
    )
    await update.message.reply_text(welcome_text)


# الرد الذكي
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(
            "حدث خطأ أثناء معالجة الطلب، حاول ثانية."
        )
        print(f"Error: {e}")


if __name__ == "__main__":
    # تشغيل خادم الويب في الخلفية
    threading.Thread(target=run_web, daemon=True).start()

    # تشغيل بوت التلغرام
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )

    print("البوت يعمل الآن على الخطة المجانية...")
    app.run_polling()
