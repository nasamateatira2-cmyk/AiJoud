import os
import re
import threading
import asyncio
import base64
from collections import defaultdict
from flask import Flask
from openai import AsyncOpenAI
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

# خادم ويب لإبقاء البوت نشطاً 24/7 على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Pro is Running with Google Imagen 3!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# قراءة المفاتيح بأمان
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# عميل المحادثة النصية
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# عميل Google لتوليد الصور
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

TARGET_MODEL = "openrouter/auto"

# ذاكرة المحادثة للمستخدمين
user_memory = defaultdict(list)
MAX_HISTORY = 6

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    welcome_text = (
        "🌟 **تم التطوير من قبل أبو الجود** 🌟\n\n"
        "أهلاً وسهلاً بك في بوت **Ai Joud** الذكي!\n\n"
        "⚡️ **المميزات المتوفرة:**\n"
        "💬 **محادثة ذكية:** يتذكر سياق الحوار بدقة.\n"
        "🎨 **توليد صور واقعية فائقة الدقة (Google Imagen 3):** اكتب مثلاً: *صمم عنكبوت أسود فوق لابتوب*.\n"
        "🖼️ **تحليل وقراءة الصور:** أرسل أي صورة وسأشرحها لك.\n"
        "🔄 **بدء محادثة جديدة:** استخدم الأمر /reset."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، تفضل بسؤالك الجديد!")

# توليد الصور الفائقة عبر Google Imagen 3
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = None
    try:
        if not gemini_client:
            await update.message.reply_text("❌ مفتاح GEMINI_API_KEY غير متصل، تأكد من إضافته في Render.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        status_msg = await update.message.reply_text("⏳ جاري إنشاء المشهد بواسطة Google Imagen 3، اذكر الله...")

        # دالة الاستدعاء المباشر لنموذج Imagen 3
        def call_imagen():
            return gemini_client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=f"A photorealistic, highly detailed, real life photograph of: {prompt}. Natural lighting, 8k resolution, cinematic atmosphere, sharp focus, wide shot.",
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1"
                )
            )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, call_imagen)

        caption_text = (
            f"🎨 **الطلب:** {prompt}\n\n"
            f"✨ **تم التطوير بواسطة:** أبو الجود"
        )

        if result.generated_images:
            image_bytes = result.generated_images[0].image.image_bytes
            await update.message.reply_photo(
                photo=image_bytes,
                caption=caption_text,
                parse_mode="Markdown"
            )
            if status_msg:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        else:
            if status_msg:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ تعذر توليد الصورة، يرجى تجربة وصف آخر."
                )

    except Exception as e:
        if status_msg:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ حدث خطأ أثناء المعالجة: {e}"
            )
        print(f"Imagen Pipeline Error: {e}")

# معالجة الرسائل وفلترة أوامر الرسم بمرونة تامة
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    pattern = r'^(صمم|صمملي|صمم\s+لي|ارسم|ارسملي|ارسم\s+لي|توليد|انشاء|انشئ|اعمل|ساوي)(\s+صورة|\s+صوره)?\s*(عن\s+|لـ\s*|ل\s+)?(.*)'
    match = re.match(pattern, user_text, re.IGNORECASE)

    if match:
        clean_prompt = match.group(4).strip()
        if clean_prompt:
            await generate_and_send_image(clean_prompt, update, context)
            return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        user_memory[user_id].append({"role": "user", "content": user_text})
        if len(user_memory[user_id]) > MAX_HISTORY:
            user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        system_prompt = (
            "أنت مساعد ذكي ومحترف اسمه Ai Joud. "
            "تم تطويرك وبرمجتك بواسطة المطور (أبو الجود). "
            "أجب دائماً بلباقة ووضوح ودقة عالية باللغة العربية."
        )

        messages = [{"role": "system", "content": system_prompt}] + user_memory[user_id]

        response = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro"},
            model=TARGET_MODEL,
            messages=messages
        )

        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المحادثة: {e}")
        print(f"Chat Error: {e}")

# قراءة وتحليل الصور
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح هذه الصورة بالتفصيل وبشكل دقيق."
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')

        response = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro"},
            model=TARGET_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_caption},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ]
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"تعذر قراءة الصورة: {e}")
        print(f"Vision Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_memory))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud Bot is running with Google Imagen 3...")
    app.run_polling(drop_pending_updates=True)
