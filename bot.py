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

# خادم داخلي لإبقاء البوت متصلاً 24/7 على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Pro is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# قراءة مفاتيح التشغيل من المتغيرات
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

TARGET_MODEL = "openrouter/auto"

# ذاكرة المحادثة
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
        "🎨 **توليد وتصميم الصور:** اكتب مثلاً: *صمم عنكبوت أسود فوق لابتوب*.\n"
        "🖼️ **تحليل وقراءة الصور:** أرسل أي صورة وسأشرحها لك بالتفصيل.\n"
        "🔄 **بدء محادثة جديدة:** استخدم الأمر /reset."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، تفضل بسؤالك الجديد!")

# توليد الصور بدقة فائقة وواقعية ومنع الوحوش والتشويه
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = None
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        status_msg = await update.message.reply_text("⏳ جاري صياغة وتوليد المشهد بدقة واقعية، اذكر الله...")

        # صياغة وتوجيه حازم للواقعية والتشريح الحقيقي
        system_instruction = (
            "You are an expert prompt engineer for FLUX image generator. "
            "Convert the user's prompt into an ultra-realistic, detailed English description. "
            "STRICT RULES:\n"
            "1. Realism: Depict realistic subjects (e.g., if a spider is requested, describe a real biological arachnid with 8 jointed legs, realistic texture, perched on a real open laptop keyboard).\n"
            "2. Strictly avoid fantasy monsters, demons, horns, evil spirits, or cartoon styles.\n"
            "3. Visuals: Macro photography, crisp natural lighting, wide angle view, sharp focus, 8k resolution.\n"
            "4. Output ONLY the raw English prompt string, without quotes or explanation."
        )

        trans_res = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro"},
            model=TARGET_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        english_prompt = trans_res.choices[0].message.content.strip().replace('"', '').replace("'", "")
        print(f"Realistic Prompt: {english_prompt}")

        encoded_prompt = urllib.parse.quote(english_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=1024&nologo=true&enhance=false"

        caption_text = (
            f"🎨 **الطلب:** {prompt}\n\n"
            f"✨ **تم التطوير بواسطة:** أبو الجود"
        )

        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as http_client:
            response = await http_client.get(image_url)

            if response.status_code == 200 and len(response.content) > 5000:
                await update.message.reply_photo(
                    photo=response.content,
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
                        text="❌ تعذر استلام الصورة من السيرفر حالياً، يرجى إعادة المحاولة."
                    )

    except Exception as e:
        if status_msg:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ حدث خطأ أثناء المعالجة: {e}"
            )
        print(f"Image Error: {e}")

# معالجة الرسائل وفلترة أوامر الرسم
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # مرونة التقاط أوامر الرسم مع الحفاظ على كلمات مثل (عنكبوت) كاملة
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

# تحليل وقراءة الصور
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

    print("Ai Joud Bot is live and ready...")
    app.run_polling(drop_pending_updates=True)
