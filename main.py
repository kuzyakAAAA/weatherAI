# импортируем стандартные и внешние библиотеки
import logging # для логирования ошибок и информации
import re # для обработки регулярных выражений при проверке формата даты
import asyncio # для работы с асинхронными функциями и событийным циклом
from datetime import datetime # для работы с датами и временем
from telegram import (
    Update, # для получения информации о сообщении и пользователе 
    ReplyKeyboardMarkup # для создания клавиатур и сообщений
)
from telegram.ext import (
    Application, # для создания и управления ботом
    CommandHandler, # для обработки команд, таких как /start и /style
    MessageHandler, # для обработки обычных сообщений от пользователей
    filters, # для фильтрации сообщений по типу (текст, команды и т.д.)
    ContextTypes # для передачи контекста между обработчиками и сохранения состояния пользователя
)
from config import BOT_TOKEN
from core.orchestrator import OutfitOrchestrator
from db.database import Database

# настройка логирования для дебага
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# константы для стилей и клавиатур
STYLES = ("casual", "business", "sport")
STYLE_BUTTONS = [["casual", "business", "sport"]]
DATE_BUTTONS = [["📅 Сегодня", "📆 Другая дата"]]

# константы текстовых сообщений для бота
MSG_CHOOSE_STYLE = "👋 Привет! Выбери свой стиль одежды:"
MSG_STYLE_INVALID = "Пожалуйста, выбери один из вариантов: casual, business, sport."
MSG_NEW_REQUEST = "✨ Жду вас с новым запросом!\nНапишите другой город или используйте /style."
MSG_CITY_PROMPT = "Теперь напиши город (на английском)."
MSG_DATE_PAST = "❌ Дата не может быть в прошлом."
MSG_DATE_FUTURE = "❌ Прогноз доступен только на ближайшие 5 дней."
MSG_DATE_INVALID = "❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД."
MSG_START_FIRST = "👋 Привет! Начните с команды /start."
MSG_LOCATION_NOT_SUPPORTED = "Пока поддерживаются только названия городов на английском."

# глобальные переменные для базы данных и orchestrator
db: Database = None
orchestrator: OutfitOrchestrator = None

# создаём клавиатуры для выбора стиля и даты
style_keyboard = ReplyKeyboardMarkup(STYLE_BUTTONS, resize_keyboard=True, one_time_keyboard=True)
date_keyboard = ReplyKeyboardMarkup(DATE_BUTTONS, resize_keyboard=True, one_time_keyboard=True)

# функция безопасной отправки сообщений пользователю с обработкой ошибок
async def safe_reply(update, text, **kwargs):
    try:
        await update.message.reply_text(text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")

# функция инициализации базы данных и orchestrator
async def init_db():
    global db, orchestrator # объявляем глобальные переменные для использования в других функциях
    db = Database() 
    await db.init_pool() # инициализируем пул соединений с базой данных
    orchestrator = OutfitOrchestrator(db=db) # создаём экземпляр orchestrator, передавая ему базу данных для доступа к данным пользователей и прогнозам погоды

# обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # пытаемся получить пользователя из базы
    try:
        user = await orchestrator.db.get_user(user_id) 
    except Exception as e:
        logging.error(f"DB error: {e}")
        await safe_reply(update, "❌ Ошибка базы данных. Попробуйте позже.")
        return

    # если пользователя нет, просим выбрать стиль
    if not user:
        await safe_reply(update, MSG_CHOOSE_STYLE, reply_markup=style_keyboard)
        context.user_data["awaiting_style"] = True
    else:
        # если есть, приветствуем и предлагаем ввести город
        await safe_reply(update, f"С возвращением! Твой стиль: {user['style']}.\n{MSG_CITY_PROMPT}")

# обработчик команды /style для смены стиля
async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, "Выбери новый стиль одежды:", reply_markup=style_keyboard)
    context.user_data["awaiting_style"] = True

# обработчик команды /cancel для сброса диалога
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await safe_reply(update, "Диалог сброшен. Напишите /start для начала.")

# обработчик выбора стиля пользователем
async def handle_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    style = update.message.text.lower()
    # проверяем корректность выбранного стиля
    if style not in STYLES:
        await safe_reply(update, MSG_STYLE_INVALID)
        return

    user_id = update.effective_user.id
    # сохраняем стиль в базе данных
    try:
        await orchestrator.db.save_user(user_id, style)
    except Exception as e:
        logging.error(f"DB error on save_user: {e}")
        await safe_reply(update, "❌ Ошибка базы данных при сохранении стиля.")
        return

    # очищаем состояние пользователя после выбора
    context.user_data.clear()
    await safe_reply(update, f"Отлично! Твой стиль обновлён: {style}. {MSG_CITY_PROMPT}")

# обработка ввода даты пользователем
async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    city = context.user_data.get("temp_city")

    # если город не указан, просим сначала ввести город
    if not city:
        context.user_data["awaiting_date"] = False
        await safe_reply(update, MSG_START_FIRST)
        return

    # обработка варианта "сегодня"
    if text == "📅 Сегодня":
        await safe_reply(update, "🔍 Смотрю погоду на сегодня...")
        recommendation = await orchestrator.get_recommendation(user_id, city)
        await safe_reply(update, recommendation, parse_mode='MARKDOWN')
        await safe_reply(update, MSG_NEW_REQUEST)
        context.user_data.clear()

    # обработка варианта "другая дата"
    elif text == "📆 Другая дата":
        context.user_data["awaiting_custom_date"] = True
        await safe_reply(update, "Введите дату в формате ГГГГ-ММ-ДД (максимум +5 дней):")

    # обработка конкретной даты формата YYYY-MM-DD
    elif re.match(r'\d{4}-\d{2}-\d{2}', text):
        target_date = text
        today = datetime.now().date() # получаем объект сегодняшней даты
        # проверяем корректность даты
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date() # преобразуем строку в объект даты
            if dt < today:
                await safe_reply(update, MSG_DATE_PAST)
                return
            if (dt - today).days > 5:
                await safe_reply(update, MSG_DATE_FUTURE)
                return
        except ValueError:
            await safe_reply(update, MSG_DATE_INVALID)
            return

        # сообщение о начале получения прогноза
        await safe_reply(update, f"🔍 Получаю прогноз на {target_date}...")

        # получаем прогноз через orchestrator
        recommendation = await orchestrator.get_recommendation_for_date(user_id, city, target_date)
        await safe_reply(update, recommendation, parse_mode='MARKDOWN')
        # сообщение о готовности к новому запросу
        await safe_reply(update, MSG_NEW_REQUEST)
        context.user_data.clear()

    # если введён некорректный текст
    else:
        await safe_reply(update, MSG_DATE_INVALID)

# основной обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # проверка состояния пользователя
    if context.user_data.get("awaiting_style"):
        await handle_style(update, context)
        return
    if context.user_data.get("awaiting_date") or context.user_data.get("awaiting_custom_date"):
        await handle_date_input(update, context)
        return

    # получение пользователя из базы
    try:
        user = await orchestrator.db.get_user(user_id)
    except Exception as e:
        logging.error(f"DB error: {e}")
        await safe_reply(update, "❌ Ошибка базы данных. Попробуйте позже.")
        return

    # если пользователя нет, просим начать с /start
    if not user:
        await safe_reply(update, MSG_START_FIRST)
        return

    # сохраняем введённый город
    city = update.message.text.strip()
    context.user_data["temp_city"] = city
    context.user_data["awaiting_date"] = True
    # спрашиваем дату
    await safe_reply(update, "📅 На какую дату нужен прогноз?", reply_markup=date_keyboard)

# функция запуска бота
def main():
    # создаём событийный цикл
    # создается отдельный планировщик задач
    loop = asyncio.new_event_loop() 
    # а здесь мы его выбираем, как рабощий для нашего кода
    asyncio.set_event_loop(loop)
    # установка соединения с бд
    loop.run_until_complete(init_db())

    # создаём приложение Telegram
    app = Application.builder().token(BOT_TOKEN).build()
    # добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("style", style_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    # добавляем обработчики сообщений и локации
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # запускаем бота
    app.run_polling()

# запуск бота
if __name__ == "__main__":
    main()
