# 👕 Weather Outfit Assistant

**Weather Outfit Assistant** — Telegram-бот, который подбирает одежду по погоде с помощью AI.

Пользователь выбирает стиль одежды, вводит город и дату, а бот получает прогноз погоды через OpenWeatherMap и формирует рекомендацию через Mistral AI.

---

## ✨ Возможности

- получение прогноза погоды по городу;
- выбор даты: сегодня или другая дата в пределах ближайших 5 дней;
- AI-рекомендации по одежде через Mistral AI;
- выбор стиля одежды: `casual`, `business`, `sport`;
- сохранение пользователей и истории запросов в PostgreSQL;
- работа с базой данных через SQLAlchemy ORM;
- смена стиля командой `/style`;
- сброс диалога командой `/cancel`;
- fallback-рекомендации, если AI временно недоступен.

---

## 🏗 Структура проекта

```text
weatherAI/
├─ clients/
│  ├─ __init__.py
│  ├─ ai_client.py           # клиент Mistral AI
│  └─ weather_client.py      # клиент OpenWeatherMap
├─ core/
│  ├─ __init__.py
│  └─ orchestrator.py        # основная логика приложения
├─ db/
│  ├─ __init__.py
│  ├─ database.py            # работа с PostgreSQL через SQLAlchemy
│  └─ scheme_of_db.md        # описание структуры базы данных
├─ __init__.py
├─ main.py                   # Telegram-бот
├─ config.py                 # конфигурация проекта
├─ config.example.py         # пример конфигурации
├─ requirements.txt          # зависимости
└─ README.md
```

## 🧩 Основные модули
- main.py — запускает Telegram-бота, обрабатывает команды, сообщения и кнопки.
- clients/weather_client.py — получает текущую погоду и прогноз через OpenWeatherMap API.
- clients/ai_client.py — отправляет данные в Mistral AI и получает текстовую рекомендацию.
- core/orchestrator.py — связывает бота, погоду, AI и базу данных.
- db/database.py — сохраняет пользователей и историю запросов в PostgreSQL.

## 🛠 Технологии

- Python
- python-telegram-bot
- aiohttp
- SQLAlchemy
- asyncpg
- PostgreSQL
- OpenWeatherMap API
- Mistral AI API

## 💬 Команды бота

- /start — начать работу с ботом;
- /style — изменить стиль одежды;
- /cancel — сбросить текущий диалог.

## 🧪 Пример работы

- Пользователь запускает бота командой /start.
- Выбирает стиль: casual, business или sport.
- Вводит город, например Moscow.
- Выбирает дату: сегодня или другую дату.
- Бот отправляет рекомендацию по одежде с учётом погоды и выбранного стиля.