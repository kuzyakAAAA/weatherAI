# импортируем необходимые модули
import logging
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN
from core.orchestrator import OutfitOrchestrator
from db.database import Database

# глобальные переменные для бд и оркестратора
db = None
orchestrator = None

async def init_db():
    # инициализируем подключение к postgres и создаём оркестратор
    global db, orchestrator
    db = Database()
    await db.init_pool()
    orchestrator = OutfitOrchestrator(db=db)

# настраиваем вывод логов в консоль
logging.basicConfig(level=logging.INFO)

# клавиатура выбора стиля одежды
style_keyboard = ReplyKeyboardMarkup(
    [["casual", "business", "sport"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# клавиатура выбора даты (сегодня или другая)
date_keyboard = ReplyKeyboardMarkup(
    [["📅 Сегодня", "📆 Другая дата"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # обрабатываем команду /start: если пользователь новый, просим выбрать стиль
    user_id = update.effective_user.id
    user = await orchestrator.db.get_user(user_id)
    if not user:
        await update.message.reply_text(
            "👋 Привет! Я помогу тебе одеться по погоде.\n"
            "Сначала выбери свой стиль одежды:",
            reply_markup=style_keyboard
        )
        context.user_data["awaiting_style"] = True
    else:
        # если пользователь уже есть, приветствуем и напоминаем команду /style
        await update.message.reply_text(
            f"С возвращением! Твой стиль: {user['style']}.\n"
            "Напиши название города (на английском), и я дам совет.\n"
            "Если хочешь сменить стиль, используй /style."
        )

async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # команда /style: предлагаем выбрать новый стиль
    await update.message.reply_text(
        "Выбери новый стиль одежды:",
        reply_markup=style_keyboard
    )
    context.user_data["awaiting_style"] = True

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # команда /cancel: сбрасываем все временные данные пользователя
    context.user_data.clear()
    await update.message.reply_text("Диалог сброшен. Напишите /start для начала.")

async def handle_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # обработчик выбора стиля: сохраняем стиль в бд и очищаем состояние
    style = update.message.text.lower()
    if style not in ["casual", "business", "sport"]:
        await update.message.reply_text("Пожалуйста, выбери один из вариантов: casual, business или sport.")
        return
    user_id = update.effective_user.id
    await orchestrator.db.save_user(user_id, style)
    context.user_data["awaiting_style"] = False
    # очищаем возможные остаточные флаги даты
    context.user_data.pop("awaiting_date", None)
    context.user_data.pop("awaiting_custom_date", None)
    context.user_data.pop("temp_city", None)
    await update.message.reply_text(
        f"Отлично! Твой стиль обновлён: {style}. Теперь напиши город (на английском)."
    )

async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # обрабатываем выбор даты после ввода города
    text = update.message.text
    user_id = update.effective_user.id
    city = context.user_data.get("temp_city")

    # если город ещё не введён, просим ввести его сначала
    if not city:
        await update.message.reply_text("Сначала введите город. Напишите название города на английском.")
        context.user_data["awaiting_date"] = False
        return

    # если пользователь ввёл дату в формате ГГГГ-ММ-ДД
    if re.match(r'\d{4}-\d{2}-\d{2}', text):
        target_date = text
        today = datetime.now().date()
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            if dt < today:
                await update.message.reply_text("❌ Дата не может быть в прошлом. Введите сегодня или будущую дату.")
                return
            if (dt - today).days > 5:
                await update.message.reply_text("❌ Прогноз доступен только на 5 дней вперёд. Введите дату не позднее +5 дней.")
                return
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД")
            return

        # получаем прогноз на указанную дату через оркестратор
        await update.message.reply_text(f"🔍 Получаю прогноз на {target_date}...")
        recommendation = await orchestrator.get_recommendation_for_date(user_id, city, target_date)
        await update.message.reply_text(recommendation)
        await update.message.reply_text("✨ Жду вас с новым запросом!\nНапишите другой город или используйте /style.")
        # сбрасываем состояния даты
        context.user_data["awaiting_date"] = False
        context.user_data["awaiting_custom_date"] = False
        context.user_data.pop("temp_city", None)
        return

    # обработка кнопки "Сегодня"
    if text == "📅 Сегодня":
        await update.message.reply_text("🔍 Смотрю погоду на сегодня...")
        recommendation = await orchestrator.get_recommendation(user_id, city, activity="walk")
        await update.message.reply_text(recommendation)
        await update.message.reply_text("✨ Жду вас с новым запросом!\nНапишите другой город или используйте /style.")
        context.user_data["awaiting_date"] = False
        context.user_data.pop("temp_city", None)

    # обработка кнопки "Другая дата" — переходим в режим ручного ввода
    elif text == "📆 Другая дата":
        await update.message.reply_text(
            "Введите дату в формате ГГГГ-ММ-ДД, например 2026-04-25\nПрогноз доступен на ближайшие 5 дней."
        )
        context.user_data["awaiting_custom_date"] = True

    # любой другой ввод — ошибка, сбрасываем диалог
    else:
        await update.message.reply_text(
            "Неверный ввод. Используйте кнопки или введите дату в формате ГГГГ-ММ-ДД.\n"
            "Чтобы начать сначала, напишите /start"
        )
        context.user_data["awaiting_date"] = False
        context.user_data.pop("awaiting_custom_date", None)
        context.user_data.pop("temp_city", None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # основной обработчик текстовых сообщений
    user_id = update.effective_user.id

    # сначала проверяем активные состояния
    if context.user_data.get("awaiting_style"):
        await handle_style(update, context)
        return

    if context.user_data.get("awaiting_date"):
        await handle_date_input(update, context)
        return

    # если пользователь не зарегистрирован, направляем к /start
    user = await orchestrator.db.get_user(user_id)
    if not user:
        await update.message.reply_text(
            "👋 Привет! Я бот-помощник по одежде.\n"
            "Пожалуйста, начни с команды /start, чтобы настроить стиль."
        )
        return

    # считаем, что пользователь ввёл город, сохраняем его и переходим к выбору даты
    city = update.message.text.strip()
    context.user_data["temp_city"] = city
    context.user_data["awaiting_date"] = True
    await update.message.reply_text(
        "📅 На какую дату нужен прогноз?",
        reply_markup=date_keyboard
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # заглушка для геолокации — пока не поддерживаем
    await update.message.reply_text("Пока я умею работать только с названиями городов. Напиши город на английском.")

def main():
    # создаём новый цикл событий, инициализируем бд и запускаем бота
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())

    # создаём приложение телеграм-бота
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("style", style_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # запускаем постоянный опрос обновлений
    app.run_polling()

if __name__ == "__main__":
    main()