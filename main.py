import os
import logging
import requests
import threading
from flask import Flask, request

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ---- STATES ----
LANG, BREAD, EXTRAS, QUANTITY, NAME, PHONE, ADDRESS, CONFIRM = range(8)

# ---- TEXTS ----
TEXT = {
    "choose_lang": {"ru": "Привет! Выберите язык:"},
    "lang_buttons": ["Русский", "English", "עברית"],
}

LANG_CODES = {"Русский": "ru", "English": "en", "עברית": "he"}

# ---- FLASK ----
app = Flask(__name__)

# ---- PTB ----
application = ApplicationBuilder().token(BOT_TOKEN).build()


# ---- HANDLERS ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton(x)] for x in TEXT["lang_buttons"]]
    await update.message.reply_text(
        TEXT["choose_lang"]["ru"],
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    return LANG


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("OK")
    return ConversationHandler.END


conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_lang)]},
    fallbacks=[],
)

application.add_handler(conv_handler)


# ---- WEBHOOK ----
@app.post("/webhook")
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    # отправляем обновление в очередь PTB
    application.update_queue.put_nowait(update)

    return "OK"


# ---- RUN PTB IN BACKGROUND ----
def run_ptb():
    application.run_polling()


threading.Thread(target=run_ptb, daemon=True).start()


# ---- START FLASK ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
