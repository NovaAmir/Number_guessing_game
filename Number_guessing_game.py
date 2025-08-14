import os
import logging
import random
import threading
import asyncio

from flask import Flask, request
from emoji import emojize

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------- تنظیمات پایه --------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("number_game")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is missing")

RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if not RENDER_HOST:
    raise RuntimeError("RENDER_EXTERNAL_HOSTNAME env var is missing")

WEBHOOK_URL = f"https://{RENDER_HOST}/webhook/{BOT_TOKEN}"

# -------------------- منطق بازی --------------------
# state ها داخل user_data نگه‌داری می‌شوند
def _reset_game(context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    ud.clear()
    ud["stage"] = "ask_min"   # مراحل: ask_min -> ask_max -> guessing
    ud["tries"] = 0

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_game(context)
    txt = emojize(
        "سلام! :game_die:\n"
        "بازی حدس عدد شروع شد.\n"
        "اول حداقلِ بازه رو بفرست (مثلاً 1)."
    )
    await update.message.reply_text(txt)
    log.info("Start command received from %s", update.effective_user.id)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_game(context)
    await update.message.reply_text("بازی ریست شد. /start رو بزن تا دوباره شروع کنیم.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("با /start بازی رو شروع کن. اول حداقل و بعد حداکثر بازه رو بفرست، بعدش شروع کن به حدس زدن!")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    ud = context.user_data
    stage = ud.get("stage")

    # مرحله گرفتن حداقل
    if stage == "ask_min":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("یک عدد صحیح برای حداقل بفرست 🙂")
        ud["min"] = int(text)
        ud["stage"] = "ask_max"
        return await update.message.reply_text("حالا حداکثر بازه رو بفرست (مثلاً 100).")

    # مرحله گرفتن حداکثر
    if stage == "ask_max":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("یک عدد صحیح برای حداکثر بفرست 🙂")
        max_v = int(text)
        min_v = ud["min"]
        if max_v <= min_v:
            return await update.message.reply_text("حداکثر باید از حداقل بزرگ‌تر باشه. دوباره بفرست.")
        ud["max"] = max_v
        ud["secret"] = random.randint(min_v, max_v)
        ud["stage"] = "guessing"
        return await update.message.reply_text(
            f"عدد مخفی انتخاب شد! بین {min_v} و {max_v} حدس بزن 👇"
        )

    # مرحله حدس زدن
    if stage == "guessing":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("فقط عدد بفرست 🙂")
        guess = int(text)
        ud["tries"] += 1
        secret = ud["secret"]
        if guess < secret:
            return await update.message.reply_text("برو بالاتر ⬆️")
        if guess > secret:
            return await update.message.reply_text("بیا پایین‌تر ⬇️")
        # درست حدس زد
        tries = ud["tries"]
        await update.message.reply_text(
            emojize(f"آفرین! درست حدس زدی :tada:\nتعداد تلاش‌ها: {tries}")
        )
        _reset_game(context)
        return await update.message.reply_text("برای دوباره بازی کردن /start رو بزن.")

    # اگر کاربر مستقیم چیزی نوشت
    return await update.message.reply_text("برای شروع بازی /start رو بزن.")

# -------------------- PTB Application --------------------
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("cancel", cancel_cmd))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# -------------------- راه‌اندازی asyncio loop اختصاصی --------------------
# روی Flask هیچ event loop فعالی نیست؛ یکی جدید می‌سازیم و همیشه روشن نگه می‌داریم.
LOOP = asyncio.new_event_loop()

def _run_loop_forever():
    asyncio.set_event_loop(LOOP)
    LOOP.run_forever()

threading.Thread(target=_run_loop_forever, daemon=True).start()

async def _ptb_init_and_webhook():
    # init/start لازم است تا application بتواند process_update را انجام بدهد
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    log.info("Webhook set to %s", WEBHOOK_URL)

# این کار را روی loop پس‌زمینه زمان‌بندی می‌کنیم
asyncio.run_coroutine_threadsafe(_ptb_init_and_webhook(), LOOP)

# -------------------- Flask app --------------------
flask_app = Flask(__name__)

@flask_app.get("/")
@flask_app.head("/")
def health():
    # برای health check های Render
    return "OK", 200

@flask_app.post(f"/webhook/{BOT_TOKEN}")
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # پردازش آپدیت روی همان loop پس‌زمینه
        asyncio.run_coroutine_threadsafe(application.process_update(update), LOOP)
        return "OK", 200
    except Exception as e:
        log.exception("webhook handler error: %s", e)
        return "ERROR", 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    log.info("Starting Flask on 0.0.0.0:%s", port)
    flask_app.run(host="0.0.0.0", port=port, debug=False)

