import os
import re
import threading
import urllib.parse
from flask import Flask
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# خادم ويب لإبقاء البوت نشطاً على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Multi-Model & Auto Image is Live!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# المفاتيح
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

TARGET_MODEL = "openrouter/auto"

# رسالة الترحيب
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud \n"
        "الاحدث والمبني على احدث انظمة الذكاء الصناعي العالمي.\n\n"
        "💡 اسألني عن أي موضوع تريده، وسأجيبك فوراً.\n"
        "🎨 لتصميم صورة، فقط قل: **صمم صورة...** أو **ارسم لي...** متبوعة بوصف ما تريد!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# دالة توليد الصور
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        await update.message.reply_photo(
            photo=image_url,
            caption=f"🎨 تم تصميم الصورة لـ: *{prompt}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"تعذر توليد الصورة: {e}")
        print(f"Draw Error: {e}")

# معالجة النصوص والتعرف التلقائي على طلبات التصميم
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    # قائمة الكلمات المفتاحية لطلب الصور
    image_triggers = [
        r"^(صمم|صمملي|صمم لي)\s+(صورة|صوره)?\s*(.*)",
        r"^(ارسم|ارسملي|ارسم لي)\s+(صورة|صوره)?\s*(.*)",
        r"^(انشئ|أنشئ|اعمل|سوي|ساوي)\s+(صورة|صوره)\s*(.*)",
        r"^(توليد صورة|انشاء صورة|توليد صوره)\s*(.*)"
    ]

    detected_prompt = None
    for pattern in image_triggers:
        match = re.match(pattern, user_text, re.IGNORECASE)
        if match:
            # استخراج وصف الصورة بعد كلمات الطلب
            detected_prompt = match.groups()[-1].strip()
            # إذا كتب فقط "صمم صورة" بدون تكملة
            if not detected_prompt:
                detected_prompt = user_text
            break

    # إذا كانت الرسالة طلباً لتصميم صورة
    if detected_prompt:
        await generate_and_send_image(detected_prompt, update, context)
        return

    # إذا كانت رسالة محادثة أو سؤال عادي
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        response = await client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://render.com",
                "X-Title": "Ai Joud Bot",
            },
            model=TARGET_MODEL,
            messages=[{"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")
        print(f"Text Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud Smart Bot Running...")
    app.run_polling(drop_pending_updates=True)
