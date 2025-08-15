import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import logging

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

# Game state
user_data = {}

# Flask app
app = Flask(__name__)

# Telegram application
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to the Number Guessing Game! Guess a number between 1 and 10.")
    user_data[update.effective_user.id] = random.randint(1, 10)

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        await update.message.reply_text("Please start the game using /start.")
        return
    try:
        guess = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return
    target = user_data[user_id]
    if guess == target:
        await update.message.reply_text("🎉 Correct! You win!")
        del user_data[user_id]
    else:
        await update.message.reply_text("❌ Wrong guess! Try again.")

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess))

# Flask route for webhook
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Set webhook URL
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not render_hostname:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME environment variable is missing")
    webhook_url = f"https://{render_hostname}/webhook/{TOKEN}"
    application.bot.set_webhook(url=webhook_url)

    # Run Flask
    app.run(host="0.0.0.0", port=port)

