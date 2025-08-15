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

# -------------------- Basic Config --------------------
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

# -------------------- Game Logic --------------------
# States are stored in user_data
def _reset_game(context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    ud.clear()
    ud["stage"] = "ask_min"   # stages: ask_min -> ask_max -> guessing
    ud["tries"] = 0

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_game(context)
    txt = emojize(
        "Hello! :waving hand:\n"
        "You started Number guessing game .\n"
        "At First, send the minimum value : "
    )
    await update.message.reply_text(txt)
    log.info("Start command received from %s", update.effective_user.id)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_game(context)
    await update.message.reply_text("Game reset. Send /start to play again.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /start to begin the game. First send the minimum, then the maximum, then start guessing!"
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    ud = context.user_data
    stage = ud.get("stage")

    # Get minimum value
    if stage == "ask_min":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("Please send an integer for the minimum 🙂")
        ud["min"] = int(text)
        ud["stage"] = "ask_max"
        return await update.message.reply_text("Now send the maximum value : ")

    # Get maximum value
    if stage == "ask_max":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("Please send an integer for the maximum 🙂")
        max_v = int(text)
        min_v = ud["min"]
        if max_v <= min_v:
            return await update.message.reply_text("Be careful maximum must be greater than minimum. Try again.")
        ud["max"] = max_v
        ud["secret"] = random.randint(min_v, max_v)
        ud["stage"] = "guessing"
        return await update.message.reply_text(
            f"The secret number is chosen! Guess between {min_v} and {max_v} 👇"
        )

    # Guessing stage
    if stage == "guessing":
        if not text.lstrip("-").isdigit():
            return await update.message.reply_text("Please send only numbers 🙂")
        guess = int(text)
        ud["tries"] += 1
        secret = ud["secret"]
        if guess < secret:
            return await update.message.reply_text("Go higher ⬆️")
        if guess > secret:
            return await update.message.reply_text("Go lower ⬇️")
        # Correct guess
        tries = ud["tries"]
        await update.message.reply_text(
            emojize(f"Congratulations! You guessed it right .\n You could guess it in {tries} tries")
        )
        _reset_game(context)
        return await update.message.reply_text("Send /start to play again.")

    # Fallback
    return await update.message.reply_text("Send /start to begin the game.")

# -------------------- PTB Application --------------------
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("cancel", cancel_cmd))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# -------------------- Dedicated asyncio loop --------------------
# We run PTB on its own event loop in a background thread
LOOP = asyncio.new_event_loop()

def _run_loop_forever():
    asyncio.set_event_loop(LOOP)
    LOOP.run_forever()

threading.Thread(target=_run_loop_forever, daemon=True).start()

async def _ptb_init_and_webhook():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    log.info("Webhook set to %s", WEBHOOK_URL)

# schedule PTB init on the background loop
asyncio.run_coroutine_threadsafe(_ptb_init_and_webhook(), LOOP)

# -------------------- Flask App --------------------
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET", "HEAD"])
def health():
    return "Bot is running", 200

def health():
    return "Bot is running", 200

@flask_app.post(f"/webhook/{BOT_TOKEN}")
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # Process update on the PTB loop
        asyncio.run_coroutine_threadsafe(application.process_update(update), LOOP)
        return "OK", 200
    except Exception as e:
        log.exception("webhook handler error: %s", e)
        return "ERROR", 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    log.info("Starting Flask on 0.0.0.0:%s", port)
    flask_app.run(host="0.0.0.0", port=port, debug=False)





