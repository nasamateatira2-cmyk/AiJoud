import os
import threading
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

# خادم ويب لإبقاء البوت نشطاً 24/7 على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Pro is Running with FLUX Engine!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# قراءة المفاتيح بأمان من Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

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
        "أهلاً وسهلاً بك في بوت Ai Joud 🌟\0\1"
         " تم تطوير البوت من قبل ابو الجود 🌟\M\A"
        "⚡️ **المميزات المتوفرة:**\n"
        "💬 **محادثة ذكية مع ذاكرة:** أرسل أي سؤال وسيتذكر سياق الحوار.\n"
        "🎨 **توليد صور FLUX عالية الدقة:** اكتب مثلاً: *صمم صورة أسد وغزال في وضح النهار*.\n"
        "🖼️ **تحليل الصور:** أرسل صورة مع سؤالك وسأشرحها لك.\n"
        "🔄 **بدء محادثة جديدة:** استخدم الأمر /reset."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، تفضل بسؤالك الجديد!")

# توليد الصور باستخدام محرك FLUX.1 عبر Hugging Face
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        status_msg = await update.message.reply_text("⏳ جاري ترجمة المشهد ورسمه بدقة عالية عبر محرك FLUX...")

        # ترجمة وضبط الموجه بدقة فائقة عبر الذكاء الاصطناعي
        system_instruction = (
            "You are an expert prompt engineer for Flux.1 image generation. "
            "Convert the user's Arabic prompt into a clean, detailed, and high-quality English visual description. "
            "Ensure ALL requested objects, animals, and background details are preserved. "
            "Focus on photorealistic daylight, vibrant colors, sharp focus, 8k resolution. "
            "Output ONLY the English prompt string without quotes, explanations, or notes."
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
        print(f"HF FLUX Prompt: {english_prompt}")

        # استدعاء نموذج FLUX.1-schnell من Hugging Face
        hf_api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {"inputs": english_prompt}

        async with httpx.AsyncClient(timeout=90.0) as http_client:
            response = await http_client.post(hf_api_url, headers=headers, json=payload)

            if response.status_code == 200 and len(response.content) > 5000:
                await update.message.reply_photo(
                    photo=response.content,
                    caption=f"🎨 **الطلب:** {prompt}\n⚡️ **المحرك:** FLUX.1 (Hugging Face)",
                    parse_mode="Markdown"
                )
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
            else:
                # إذا كان السيرفر مشغولاً أو استجاب برمز خطأ
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ لم يتمكن السيرفر من معالجة الصورة في الوقت الحالي، أعد المحاولة بعد لحظات."
                )
                print(f"HF Error Status: {response.status_code}, Details: {response.text}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء الرسم: {e}")
        print(f"Image Pipeline Error: {e}")

# معالجة الرسائل النصية
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    image_keywords = [
        "صمم صورة", "صمملي صورة", "صمم لي صورة",
        "ارسم صورة", "ارسملي صورة", "ارسم لي صورة",
        "صمم صوره", "صمملي صوره", "ارسم صوره", "ارسملي صوره",
        "توليد صورة", "انشاء صورة", "انشئ صورة", "اعمل صورة", "ساوي صورة"
    ]

    is_image_request = False
    clean_prompt = user_text

    for kw in image_keywords:
        if user_text.startswith(kw):
            is_image_request = True
            clean_prompt = user_text[len(kw):].strip()
            # تنظيف حروف الجر الزائدة في بداية الطلب
            if clean_prompt.startswith("لـ") or clean_prompt.startswith("لا"):
                clean_prompt = clean_prompt[1:].strip()
            elif clean_prompt.startswith("عن"):
                clean_prompt = clean_prompt[2:].strip()
            break

    if is_image_request and clean_prompt:
        await generate_and_send_image(clean_prompt, update, context)
        return

    # الردود الذكية العادية مع الذاكرة
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        user_memory[user_id].append({"role": "user", "content": user_text})
        if len(user_memory[user_id]) > MAX_HISTORY:
            user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        messages = [
            {"role": "system", "content": "أنت مساعد ذكي ولطيف اسمه Ai Joud. تجيب باحترافية، وضوح، وتفصيل مفيد باللغة العربية."}
        ] + user_memory[user_id]

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

# تحليل الصور
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

    print("Ai Joud with FLUX is running smoothly...")
    app.run_polling(drop_pending_updates=True)
