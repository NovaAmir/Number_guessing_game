import os
import random
import threading
import emoji
from flask import Flask
from telegram import Update
from telegram.ext import (
    CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackContext, Application
)

GET_MIN, GET_MAX, GET_GUESS, PLAY_AGAIN = range(4)

# --------- Flask keep-alive server (for Render & UptimeRobot) ----------
def make_http_app():
    http_app = Flask(__name__)

    @http_app.get("/")
    def index():
        return "OK", 200

    return http_app

def run_http_server():
    # Render پورت را در متغیر PORT می‌دهد
    port = int(os.getenv("PORT", "10000"))
    http_app = make_http_app()
    # سرور سبک برای پینگ UptimeRobot کفایت می‌کند
    http_app.run(host="0.0.0.0", port=port)

# ---------------------- Telegram Bot Handlers --------------------------
async def welcome(update: Update, context: CallbackContext) -> int:
    message = emoji.emojize(
        "Hi:waving_hand:\n"
        "I'm AmirNova and I'm glad you started Number guessing game:fire:\n\n"
        "At first you must choose two numbers to make a range of number\n"
        "Second , I select a number from your range\n"
        "finally , you must guess it\n"
        "I hope you enjoy it:smiling_face:"
    )
    await update.message.reply_text(message)
    await update.message.reply_text("Enter the minimum number of the range :")
    return GET_MIN

async def make_randint(update: Update, context: CallbackContext) -> int:
    try:
        min_num = int(update.message.text)
        context.user_data['min_num'] = min_num
        await update.message.reply_text("Now enter the maximum number of the range : ")
        return GET_MAX
    except ValueError:
        await update.message.reply_text("Please enter a valid number!")
        return GET_MIN

async def start_game(update: Update, context: CallbackContext) -> int:
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

async def get_a_guess(update: Update, context: CallbackContext) -> int:
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
        return emoji.emojize("your number is bigger than correct number ! please choose smaller one :down_arrow:")
    else:
        return emoji.emojize("your number is smaller than correct number ! please choose bigger one :up_arrow:")

async def finish(update: Update, context: CallbackContext) -> int:
    true_num = context.user_data['True_num']
    count = context.user_data['count']
    await update.message.reply_text(
        emoji.emojize(f"Excellent! The number was {true_num} . You guessed it in {count} tries.")
    )
    await update.message.reply_text(emoji.emojize("Do you want to Play again? :thinking_face:(Yes/No)"))
    return PLAY_AGAIN

async def play_again(update: Update, context: CallbackContext) -> int:
    response = update.message.text.lower()
    if response == 'yes':
        await update.message.reply_text("Enter the minimum number : ")
        return GET_MIN
    else:
        await update.message.reply_text(emoji.emojize("Thanks for playing:smiling_face:\n See you later"))
        return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Game canceled. Type /start to play again.")
    return ConversationHandler.END

def main():
    # توکن را از Environment Variable بگیر
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var is missing")

    # سرور HTTP را در یک ترد جدا روشن کن تا Render پورت را ببیند
    threading.Thread(target=run_http_server, daemon=True).start()

    # برنامه‌ی تلگرام
    tg_app = Application.builder().token(token).build()

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
    tg_app.add_handler(conv_handler)

    print("Bot is running")
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

    
   



       
        

    



