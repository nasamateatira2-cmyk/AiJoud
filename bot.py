import os
import re
import threading
import urllib.parse
import base64
from collections import defaultdict
from flask import Flask
import httpx
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
    return "Ai Joud Pro is Live & Fast!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# جلب المفاتيح من متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

TARGET_MODEL = "openrouter/auto"

# ذاكرة المحادثات لكل مستخدم (حفظ آخر 6 رسائل لسرعة ودقة الاستجابة)
user_memory = defaultdict(list)
MAX_HISTORY = 6

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    welcome_text = (
        "اهلا وسهلا بك يا غالي في بوت الذكاء الصناعي Ai Joud 🌟\n\n"
        "⚡️ **القدرات المتاحة:**\n"
        "💬 **سياق ذكي:** أتذكر سياق حديثك وأفهم ما تشير إليه.\n"
        "🎨 **تصميم صور احترافي:** اطلب مباشرة: *صمم صورة...* وسأرسمها بدقة ووضوح.\n"
        "🖼️ **تحليل الصور:** أرسل أي صورة وسأشرح محتواها بالكامل.\n"
        "🔄 **بدء محادثة جديدة:** أرسل الأمر /reset في أي وقت."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، يمكنك بدء محادثة جديدة الآن!")

# توليد الصور مع صياغة سينمائية نهارية لضمان تفصيل كل عنصر
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")

        system_instruction = (
            "You are an expert prompt engineer for photorealistic image generation. "
            "Convert the user prompt into a high-detail, vivid daylight scene. "
            "Explicitly list each requested animal or object separately, specifying their realistic scale, appearance, and positions without blending them together. "
            "Include keywords: 'bright daylight, clear details, National Geographic style photography, sharp focus, 8k resolution'. "
            "Output ONLY the English prompt text without quotes or explanation."
        )

        trans_res = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro Bot"},
            model=TARGET_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        english_prompt = trans_res.choices[0].message.content.strip()

        encoded_prompt = urllib.parse.quote(english_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024&nologo=true&seed={os.urandom(4).hex()}"

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            res = await http_client.get(image_url)
            if res.status_code == 200:
                await update.message.reply_photo(
                    photo=res.content,
                    caption=f"🎨 تم تصميم الصورة لـ: *{prompt}*",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("تعذر إنشاء الصورة حالياً من الخادم، يرجى المحاولة بعد قليل.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء التصميم: {e}")
        print(f"Draw Error: {e}")

# معالجة الرسائل النصية والمحادثة المعتمدة على السياق
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # فحص الكلمات المفتاحية لتصميم الصور
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
            detected_prompt = match.groups()[-1].strip() or user_text
            break

    if detected_prompt:
        await generate_and_send_image(detected_prompt, update, context)
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        user_memory[user_id].append({"role": "user", "content": user_text})
        if len(user_memory[user_id]) > MAX_HISTORY:
            user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        messages = [
            {"role": "system", "content": "أنت مساعد ذكي ولطيف اسمه Ai Joud. تجيب بدقة واحترافية وباللغة العربية الفصحى أو بلهجة المستخدم الودية."}
        ] + user_memory[user_id]

        response = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro Bot"},
            model=TARGET_MODEL,
            messages=messages
        )
        
        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {e}")
        print(f"Chat Error: {e}")

# معالجة وتحليل الصور المرسلة
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_caption = update.message.caption or "اشرح هذه الصورة بالتفصيل والوضوح، واذكر أهم العناصر الظاهرة فيها."
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')

        response = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro Bot"},
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
        await update.message.reply_text(f"تعذر تحليل الصورة: {e}")
        print(f"Photo Error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_memory))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud Ultimate Flux is running...")
    app.run_polling(drop_pending_updates=True)
