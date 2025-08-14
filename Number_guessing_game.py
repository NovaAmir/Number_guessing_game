import os
import random
import emoji
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)

GET_MIN, GET_MAX, GET_GUESS, PLAY_AGAIN = range(4)

# ---------------------- Telegram Bot Handlers --------------------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = emoji.emojize(
        "Hi :waving_hand:\n"
        "I'm AmirNova and I'm glad you started Number guessing game :fire:\n\n"
        "At first you must choose two numbers to make a range of number\n"
        "Second , I select a number from your range\n"
        "finally , you must guess it\n"
        "I hope you enjoy it :smiling_face:"
    )
    await update.message.reply_text(message)
    await update.message.reply_text("Enter the minimum number of the range :")
    return GET_MIN

async def make_randint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        min_num = int(update.message.text)
        context.user_data['min_num'] = min_num
        await update.message.reply_text("Now enter the maximum number of the range : ")
        return GET_MAX
    except ValueError:
        await update.message.reply_text("Please enter a valid number!")
        return GET_MIN

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        max_num = int(update.message.text)
        min_num = context.user_data['min_num']

        if min_num >= max_num:
            await update.message.reply_text("Minimum must be smaller than maximum. Game starts from the beginning, be careful!")
            await update.message.reply_text("Enter the minimum number of the range :")
            return GET_MIN

        true_num = random.randint(min_num, max_num)
        context.user_data.update({'True_num': true_num, 'max_num': max_num, 'count': 0})

        await update.message.reply_text(f"Guess a number between {min_num} and {max_num} : ")
        return GET_GUESS
    except ValueError:
        await update.message.reply_text("Please enter a valid number!")
        return GET_MAX

async def get_a_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        guess = int(update.message.text)
        true_num = context.user_data['True_num']
        min_num = context.user_data['min_num']
        max_num = context.user_data['max_num']
        context.user_data['count'] += 1

        if guess < min_num or guess > max_num:
            await update.message.reply_text(f"Enter a number between {min_num} and {max_num}!")
            return GET_GUESS
        if true_num == guess:
            return await finish(update, context)
        else:
            await update.message.reply_text(await rahnama(true_num, guess))
            return GET_GUESS
    except ValueError:
        await update.message.reply_text("Please enter a valid number!")
        return GET_GUESS

async def rahnama(true_num: int, guess: int) -> str:
    if guess > true_num:
        return emoji.emojize("your number is bigger than correct number! choose smaller :down_arrow:")
    else:
        return emoji.emojize("your number is smaller than correct number! choose bigger :up_arrow:")

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    true_num = context.user_data['True_num']
    count = context.user_data['count']
    await update.message.reply_text(
        emoji.emojize(f"Excellent! The number was {true_num} . You guessed it in {count} tries.")
    )
    await update.message.reply_text(emoji.emojize("Do you want to Play again? :thinking_face: (Yes/No)"))
    return PLAY_AGAIN

async def play_again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text.lower()
    if response == 'yes':
        await update.message.reply_text("Enter the minimum number : ")
        return GET_MIN
    else:
        await update.message.reply_text(emoji.emojize("Thanks for playing :smiling_face:\n See you later"))
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Game canceled. Type /start to play again.")
    return ConversationHandler.END

# ---------------------- Flask + Webhook --------------------------
flask_app = Flask(__name__)
application = None

@flask_app.route('/')
def home():
    return "Bot is running with Webhook!"

@flask_app.route(f"/webhook/{os.getenv('BOT_TOKEN')}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

async def set_webhook_and_run():
    global application
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var is missing")

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', welcome)],
        states={
            GET_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, make_randint)],
            GET_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_game)],
            GET_GUESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_a_guess)],
            PLAY_AGAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, play_again)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)

    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not render_hostname:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME env var is missing")
    webhook_url = f"https://{render_hostname}/webhook/{token}"

    await application.bot.delete_webhook()
    await application.bot.set_webhook(url=webhook_url)

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook_and_run())
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

