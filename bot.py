import os
import threading
from collections import defaultdict
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

# خادم داخلي لإبقاء البوت نشطاً على Render مدار الساعة
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ai Joud is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# قراءة مفاتيح التشغيل من متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# نموذج الدردشة الذكي والمستقر
CHAT_MODEL = "openrouter/auto"

# إدارة ذاكرة المحادثة لكل مستخدم
user_memory = defaultdict(list)
MAX_HISTORY = 6

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    welcome_text = (
        "🌟 **تم التطوير من قبل أبو الجود** 🌟\n\n"
        "أهلاً وسهلاً بك في بوت **Ai Joud** الذكي!\n\n"
        "⚡️ **المميزات المتوفرة:**\n"
        "💬 **محادثة ذكية:** إجابات دقيقة وسريعة مع تذكر سياق الحوار بالكامل.\n"
        "🔄 **بدء محادثة جديدة:** استخدم الأمر /reset لمسح الذاكرة.\n\n"
        "✨ أرسل سؤالك أو استفسارك وسأجيبك فوراً!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("🔄 تم مسح الذاكرة بنجاح، تفضل بسؤالك الجديد!")

# معالجة النصوص واعتراض طلبات تصميم الصور
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # رصد أوامر طلب الرسم والتصميم
    is_image_request = (
        any(user_text.startswith(t) for t in ["صمم", "ارسم", "توليد", "انشئ", "ساوي", "اعمل"]) or
        ("صورة" in user_text and any(w in user_text for w in ["بدي", "اريد", "اعمللي", "صمملي", "ارسملي"]))
    )

    if is_image_request:
        notice_text = (
            "🎨 **ميزة توليد وتصميم الصور قيد التطوير والتحديث حالياً.**\n\n"
            "ستتوفر قريباً بإذن الله بجودة عالية! ✨\n"
            "يمكنك حالياً الاستفادة من المحادثة الذكية والإجابة عن كافة استفساراتك."
        )
        await update.message.reply_text(notice_text, parse_mode="Markdown")
        return

    # المحادثة الذكية
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        user_memory[user_id].append({"role": "user", "content": user_text})
        if len(user_memory[user_id]) > MAX_HISTORY:
            user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        system_prompt = (
            "أنت مساعد ذكي ومحترف اسمه Ai Joud. "
            "تم تطويرك وبرمجتك بواسطة المطور (أبو الجود). "
            "أجب دائماً بلباقة ووضوح ودقة باللغة العربية."
        )

        messages = [{"role": "system", "content": system_prompt}] + user_memory[user_id]

        response = await client.chat.completions.create(
            extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "Ai Joud Pro"},
            model=CHAT_MODEL,
            messages=messages,
            max_tokens=1000
        )

        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المحادثة: {e}")
        print(f"Chat Error: {e}")

# اعتراض إرسال الصور والرد بلباقة دون استدعاء أي نموذج يسبب أخطاء
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_msg = (
        "🖼️ **ميزة تحليل وقراءة الصور قيد الصيانة والتطوير حالياً.**\n\n"
        "ستتوفر قريباً بدقة أعلى إن شاء الله! ✨\n"
        "تفضل بطرح أي سؤال أو موضوع عبر الرسائل النصية وسأجيبك فوراً."
    )
    await update.message.reply_text(reply_msg, parse_mode="Markdown")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_memory))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Ai Joud Bot is running stably in chat mode...")
    app.run_polling(drop_pending_updates=True)
