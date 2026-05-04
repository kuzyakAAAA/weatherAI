import logging
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN
from core.orchestrator import OutfitOrchestrator
from db.database import Database

# ----------------- Логирование -----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ----------------- Константы -----------------
STYLES = ("casual", "business", "sport")
STYLE_BUTTONS = [["casual", "business", "sport"]]
DATE_BUTTONS = [["📅 Сегодня", "📆 Другая дата"]]

MSG_CHOOSE_STYLE = "👋 Привет! Выбери свой стиль одежды:"
MSG_STYLE_INVALID = "Пожалуйста, выбери один из вариантов: casual, business, sport."
MSG_NEW_REQUEST = "✨ Жду вас с новым запросом!\nНапишите другой город или используйте /style."
MSG_CITY_PROMPT = "Теперь напиши город (на английском)."
MSG_DATE_PAST = "❌ Дата не может быть в прошлом."
MSG_DATE_FUTURE = "❌ Прогноз доступен только на ближайшие 5 дней."
MSG_DATE_INVALID = "❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД."
MSG_START_FIRST = "👋 Привет! Начните с команды /start."
MSG_LOCATION_NOT_SUPPORTED = "Пока поддерживаются только названия городов на английском."

# ----------------- Глобальные переменные -----------------
db: Database = None
orchestrator: OutfitOrchestrator = None

# ----------------- Клавиатуры -----------------
style_keyboard = ReplyKeyboardMarkup(STYLE_BUTTONS, resize_keyboard=True, one_time_keyboard=True)
date_keyboard = ReplyKeyboardMarkup(DATE_BUTTONS, resize_keyboard=True, one_time_keyboard=True)

# ----------------- Вспомогательная функция -----------------
async def safe_reply(update, text, **kwargs):
    try:
        await update.message.reply_text(text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")

# ----------------- Инициализация базы -----------------
async def init_db():
    global db, orchestrator
    db = Database()
    await db.init_pool()
    orchestrator = OutfitOrchestrator(db=db)

# ----------------- Обработчики -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        user = await orchestrator.db.get_user(user_id)
    except Exception as e:
        logging.error(f"DB error: {e}")
        await safe_reply(update, "❌ Ошибка базы данных. Попробуйте позже.")
        return

    if not user:
        await safe_reply(update, MSG_CHOOSE_STYLE, reply_markup=style_keyboard)
        context.user_data["awaiting_style"] = True
    else:
        await safe_reply(update, f"С возвращением! Твой стиль: {user['style']}.\n{MSG_CITY_PROMPT}")

async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, "Выбери новый стиль одежды:", reply_markup=style_keyboard)
    context.user_data["awaiting_style"] = True

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await safe_reply(update, "Диалог сброшен. Напишите /start для начала.")

async def handle_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    style = update.message.text.lower()
    if style not in STYLES:
        await safe_reply(update, MSG_STYLE_INVALID)
        return

    user_id = update.effective_user.id
    try:
        await orchestrator.db.save_user(user_id, style)
    except Exception as e:
        logging.error(f"DB error on save_user: {e}")
        await safe_reply(update, "❌ Ошибка базы данных при сохранении стиля.")
        return

    context.user_data.clear()
    await safe_reply(update, f"Отлично! Твой стиль обновлён: {style}. {MSG_CITY_PROMPT}")

async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    city = context.user_data.get("temp_city")

    if not city:
        context.user_data["awaiting_date"] = False
        await safe_reply(update, MSG_START_FIRST)
        return

    # ---------------- Сегодня ----------------
    if text == "📅 Сегодня":
        await safe_reply(update, "🔍 Смотрю погоду на сегодня...")
        recommendation = await orchestrator.get_recommendation(user_id, city)
        await safe_reply(update, recommendation)
        await safe_reply(update, MSG_NEW_REQUEST)
        context.user_data.clear()

    # ---------------- Другая дата ----------------
    elif text == "📆 Другая дата":
        context.user_data["awaiting_custom_date"] = True
        await safe_reply(update, "Введите дату в формате ГГГГ-ММ-ДД (максимум +5 дней):")

    # ---------------- Дата в формате YYYY-MM-DD ----------------
    elif re.match(r'\d{4}-\d{2}-\d{2}', text):
        target_date = text
        today = datetime.now().date()
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            if dt < today:
                await safe_reply(update, MSG_DATE_PAST)
                return
            if (dt - today).days > 5:
                await safe_reply(update, MSG_DATE_FUTURE)
                return
        except ValueError:
            await safe_reply(update, MSG_DATE_INVALID)
            return

        # 🔍 Сообщение о начале получения прогноза
        await safe_reply(update, f"🔍 Получаю прогноз на {target_date}...")

        recommendation = await orchestrator.get_recommendation_for_date(user_id, city, target_date)
        await safe_reply(update, recommendation)
        await safe_reply(update, MSG_NEW_REQUEST)
        context.user_data.clear()

    else:
        await safe_reply(update, MSG_DATE_INVALID)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.user_data.get("awaiting_style"):
        await handle_style(update, context)
        return
    if context.user_data.get("awaiting_date") or context.user_data.get("awaiting_custom_date"):
        await handle_date_input(update, context)
        return

    try:
        user = await orchestrator.db.get_user(user_id)
    except Exception as e:
        logging.error(f"DB error: {e}")
        await safe_reply(update, "❌ Ошибка базы данных. Попробуйте позже.")
        return

    if not user:
        await safe_reply(update, MSG_START_FIRST)
        return

    city = update.message.text.strip()
    context.user_data["temp_city"] = city
    context.user_data["awaiting_date"] = True
    await safe_reply(update, "📅 На какую дату нужен прогноз?", reply_markup=date_keyboard)

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, MSG_LOCATION_NOT_SUPPORTED)

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("style", style_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    app.run_polling()

if __name__ == "__main__":
    main()