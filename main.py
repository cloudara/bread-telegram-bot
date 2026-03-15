import os
import logging
import requests
from flask import Flask, request

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
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

# ---- ENV ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # твой chat_id

# ---- STATES ----
LANG, BREAD, EXTRAS, QUANTITY, NAME, PHONE, ADDRESS, CONFIRM = range(8)

# ---- TEXTS ----
TEXT = {
    "choose_lang": {
        "ru": "Привет! Выберите язык:",
        "en": "Hello! Choose your language:",
        "he": "שלום! בחר שפה:",
    },
    "lang_buttons": ["Русский", "English", "עברית"],
    "order": {
        "ru": "Сделать заказ",
        "en": "Make an order",
        "he": "בצע הזמנה",
    },
    "start_order": {
        "ru": "Нажмите кнопку, чтобы оформить заказ:",
        "en": "Tap the button to place an order:",
        "he": "לחץ על הכפתור כדי לבצע הזמנה:",
    },
    "choose_bread": {
        "ru": "Выберите вид хлеба:",
        "en": "Choose bread type:",
        "he": "בחר סוג לחם:",
    },
    "bread_white": {
        "ru": "Белый",
        "en": "White",
        "he": "לבן",
    },
    "bread_whole": {
        "ru": "Цельнозерновой",
        "en": "Whole grain",
        "he": "מלא",
    },
    "choose_extras": {
        "ru": "Добавить что‑нибудь?",
        "en": "Any extras?",
        "he": "להוסיף משהו?",
    },
    "extra_seeds": {
        "ru": "Семечки",
        "en": "Seeds",
        "he": "גרעינים",
    },
    "extra_olives": {
        "ru": "Оливки",
        "en": "Olives",
        "he": "זיתים",
    },
    "extra_none": {
        "ru": "Без добавок",
        "en": "No extras",
        "he": "בלי תוספות",
    },
    "quantity": {
        "ru": "Введите количество:",
        "en": "Enter quantity:",
        "he": "הכנס כמות:",
    },
    "name": {
        "ru": "Введите ваше имя:",
        "en": "Enter your name:",
        "he": "הכנס שם:",
    },
    "phone": {
        "ru": "Введите номер телефона:",
        "en": "Enter your phone number:",
        "he": "הכנס מספר טלפון:",
    },
    "address": {
        "ru": "Введите адрес доставки:",
        "en": "Enter delivery address:",
        "he": "הכנס כתובת משלוח:",
    },
    "confirm_title": {
        "ru": "Проверьте заказ:",
        "en": "Check your order:",
        "he": "בדוק את ההזמנה:",
    },
    "confirm_button": {
        "ru": "Подтвердить заказ",
        "en": "Confirm order",
        "he": "אשר הזמנה",
    },
    "cancel_button": {
        "ru": "Отменить",
        "en": "Cancel",
        "he": "בטל",
    },
    "confirmed": {
        "ru": "Спасибо! Заказ принят.",
        "en": "Thank you! Your order is accepted.",
        "he": "תודה! ההזמנה התקבלה.",
    },
    "cancelled": {
        "ru": "Заказ отменён.",
        "en": "Order cancelled.",
        "he": "ההזמנה בוטלה.",
    },
    "invalid_number": {
        "ru": "Пожалуйста, введите число.",
        "en": "Please enter a number.",
        "he": "אנא הזן מספר.",
    },
}

LANG_CODES = {
    "Русский": "ru",
    "English": "en",
    "עברית": "he",
}

# ---- FLASK + PTB ----
app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()


def t(key: str, lang: str) -> str:
    return TEXT.get(key, {}).get(lang, TEXT.get(key, {}).get("en", ""))


def bread_label_to_code(label: str, lang: str) -> str:
    if label == t("bread_white", lang):
        return "white"
    if label == t("bread_whole", lang):
        return "whole"
    return "unknown"


def extras_labels_to_codes(labels, lang: str):
    codes = []
    for l in labels:
        if l == t("extra_seeds", lang):
            codes.append("seeds")
        elif l == t("extra_olives", lang):
            codes.append("olives")
        elif l == t("extra_none", lang):
            codes.append("none")
    return codes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton(x)] for x in TEXT["lang_buttons"]]
    await update.message.reply_text(
        TEXT["choose_lang"]["ru"],  # стартовое сообщение можно на русском
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True),
    )
    return LANG


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in LANG_CODES:
        kb = [[KeyboardButton(x)] for x in TEXT["lang_buttons"]]
        await update.message.reply_text(
            "Пожалуйста, выберите язык из кнопок.",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True),
        )
        return LANG

    lang = LANG_CODES[choice]
    context.user_data["lang"] = lang

    kb = [[KeyboardButton(t("order", lang))]]
    await update.message.reply_text(
        t("start_order", lang),
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    return BREAD


async def choose_bread_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    if update.message.text != t("order", lang):
        kb = [[KeyboardButton(t("order", lang))]]
        await update.message.reply_text(
            t("start_order", lang),
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        )
        return BREAD

    kb = [
        [KeyboardButton(t("bread_white", lang))],
        [KeyboardButton(t("bread_whole", lang))],
    ]
    await update.message.reply_text(
        t("choose_bread", lang),
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    return EXTRAS


async def choose_extras_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    bread_label = update.message.text
    context.user_data["bread_label"] = bread_label
    context.user_data["bread_code"] = bread_label_to_code(bread_label, lang)

    kb = [
        [KeyboardButton(t("extra_seeds", lang)), KeyboardButton(t("extra_olives", lang))],
        [KeyboardButton(t("extra_none", lang))],
    ]
    await update.message.reply_text(
        t("choose_extras", lang),
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    return QUANTITY


async def quantity_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    extra_label = update.message.text
    context.user_data["extras_labels"] = [extra_label]
    context.user_data["extras_codes"] = extras_labels_to_codes([extra_label], lang)

    await update.message.reply_text(t("quantity", lang), reply_markup=None)
    return NAME


async def name_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    text = update.message.text
    if not text.isdigit():
        await update.message.reply_text(t("invalid_number", lang))
        return NAME

    context.user_data["quantity"] = int(text)
    await update.message.reply_text(t("name", lang))
    return PHONE


async def phone_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    context.user_data["name"] = update.message.text
    await update.message.reply_text(t("phone", lang))
    return ADDRESS


async def address_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    context.user_data["phone"] = update.message.text
    await update.message.reply_text(t("address", lang))
    return CONFIRM


async def confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    context.user_data["address"] = update.message.text

    bread = context.user_data["bread_label"]
    extras = ", ".join(context.user_data["extras_labels"])
    qty = context.user_data["quantity"]
    name = context.user_data["name"]
    phone = context.user_data["phone"]
    addr = context.user_data["address"]

    summary = (
        f"{t('confirm_title', lang)}\n\n"
        f"{'Хлеб' if lang=='ru' else 'Bread' if lang=='en' else 'לחם'}: {bread}\n"
        f"{'Добавки' if lang=='ru' else 'Extras' if lang=='en' else 'תוספות'}: {extras}\n"
        f"{'Количество' if lang=='ru' else 'Quantity' if lang=='en' else 'כמות'}: {qty}\n"
        f"{'Имя' if lang=='ru' else 'Name' if lang=='en' else 'שם'}: {name}\n"
        f"{'Телефон' if lang=='ru' else 'Phone' if lang=='en' else 'טלפון'}: {phone}\n"
        f"{'Адрес' if lang=='ru' else 'Address' if lang=='en' else 'כתובת'}: {addr}\n"
    )

    kb = [
        [KeyboardButton(t("confirm_button", lang))],
        [KeyboardButton(t("cancel_button", lang))],
    ]
    await update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    return ConversationHandler.END


async def handle_confirm_or_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    text = update.message.text

    if text == t("confirm_button", lang):
        await save_order_to_airtable(context.user_data, lang)
        await send_order_to_admin(context.user_data, lang, update)
        await update.message.reply_text(t("confirmed", lang), reply_markup=None)
    else:
        await update.message.reply_text(t("cancelled", lang), reply_markup=None)

    context.user_data.clear()
    return ConversationHandler.END


async def save_order_to_airtable(data: dict, lang: str):
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID):
        logger.warning("Airtable env vars not set, skipping save.")
        return

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }

    bread = data.get("bread_code")
    extras = data.get("extras_codes", [])
    qty = data.get("quantity")
    name = data.get("name")
    phone = data.get("phone")
    addr = data.get("address")

    payload = {
        "fields": {
            "Bread": bread,
            "Extras": extras,
            "Quantity": qty,
            "Name": name,
            "Phone": phone,
            "Address": addr,
            "Language": lang,
        }
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Airtable error: {e}")


async def send_order_to_admin(data: dict, lang: str, update: Update):
    if not ADMIN_CHAT_ID:
        return

    bread = data.get("bread_label")
    extras = ", ".join(data.get("extras_labels", []))
    qty = data.get("quantity")
    name = data.get("name")
    phone = data.get("phone")
    addr = data.get("address")

    msg = (
        f"Новый заказ (lang={lang}):\n"
        f"User: @{update.effective_user.username} (id={update.effective_user.id})\n\n"
        f"Хлеб: {bread}\n"
        f"Добавки: {extras}\n"
        f"Количество: {qty}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Адрес: {addr}\n"
    )

    await application.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(t("cancelled", lang))
    context.user_data.clear()
    return ConversationHandler.END


# ---- PTB HANDLERS ----
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_lang)],
        BREAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_bread_entry)],
        EXTRAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_extras_entry)],
        QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_entry)],
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_entry)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_entry)],
        ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_entry)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,
)

application.add_handler(conv_handler)
application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm_or_cancel)
)


# ---- WEBHOOK ENDPOINT ----
@app.post("/webhook")
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.update_queue.put_nowait(update)
    return "OK"


if __name__ == "__main__":
    # Локально можно тестировать через polling:
    # application.run_polling()
    # На Render — запуск через gunicorn/uvicorn, Flask берёт на себя входящий HTTP.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
