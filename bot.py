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

# خادم ويب لإبقاء البوت نشطاً 24/7 على Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud Pro is Running 24/7!"

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
        "🌟 **تم التطوير من قبل أبو الجود** 🌟\n\n"
        "أهلاً وسهلاً بك في بوت **Ai Joud** الذكي!\n\n"
        "⚡️ **المميزات المتوفرة:**\n"
        "💬 **محادثة ذكية مع ذاكرة:** أرسل أي سؤال وسيتذكر سياق الحوار.\n"
        "🎨 **توليد وتصميم الصور:** اكتب مثلاً: *صمم عنكبوت أسود فوق لابتوب* أو *ارسم صورة أسد وغزال*.\n"
        "🖼️ **تحليل الصور:** أرسل أي صورة وسأشرحها لك بالتفصيل.\n"
        "🔄 **بدء محادثة جديدة:** استخدم الأمر /reset."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، تفضل بسؤالك الجديد!")

# توليد الصور مع ترجمة دقيقة ومحرك بديل فوري
async def generate_and_send_image(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = None
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        status_msg = await update.message.reply_text("⏳ جاري صياغة وتوليد المشهد بدقة عالية، اذكر الله...")

        system_instruction = (
            "You are an expert prompt engineer. "
            "Convert the user's Arabic description into a single cohesive, highly detailed English prompt for SDXL / Flux. "
            "Ensure ALL requested objects and details are explicitly described. "
            "Output ONLY the English prompt string, no quotes or notes."
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
        print(f"Final Image Prompt: {english_prompt}")

        api_url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {"inputs": english_prompt}

        caption_text = (
            f"🎨 **الطلب:** {prompt}\n\n"
            f"✨ **تم التطوير بواسطة:** أبو الجود"
        )

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
            response = await http_client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200 and len(response.content) > 5000:
                await update.message.reply_photo(
                    photo=response.content,
                    caption=caption_text,
                    parse_mode="Markdown"
                )
                if status_msg:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
            else:
                # خادم بديل تلقائي في حال انشغال السيرفر الأول
                encoded = urllib.parse.quote(english_prompt)
                fallback_url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true"
                fb_res = await http_client.get(fallback_url)
                if fb_res.status_code == 200 and len(fb_res.content) > 5000:
                    await update.message.reply_photo(
                        photo=fb_res.content,
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
                            text="❌ تعذر معالجة الصورة حالياً، يرجى المحاولة بعد قليل."
                        )

    except Exception as e:
        if status_msg:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ حدث خطأ أثناء المعالجة: {e}"
            )
        print(f"Pipeline Error: {e}")

# معالجة الرسائل وفلترة طلبات الرسم بدقة عالية ومرونة
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # التقاط صيغ الرسم سواء ذُكرت كلمة (صورة) أم لا، مع الحفاظ على كلمات مثل "عنكبوت"
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

    print("Ai Joud Bot is fully operational...")
    app.run_polling(drop_pending_updates=True)
