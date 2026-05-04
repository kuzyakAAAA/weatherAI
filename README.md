# 👕 Weather Outfit Assistant — Telegram бот

Telegram-бот, который помогает подобрать одежду по погоде с использованием AI (Mistral AI).  
Пользователь указывает город и дату, бот получает прогноз погоды и генерирует персонализированную рекомендацию с учётом выбранного стиля: **casual / business / sport**.

---

## ✨ Возможности

- 📍 Получение погоды на **сегодня** или на любую дату в пределах 5 дней  
- 🤖 AI‑рекомендации через **Mistral AI** (прямые HTTP-запросы, без сторонних библиотек)  
- 👔 Выбор стиля одежды: casual, business, sport  
- 💾 История запросов и сохранение настроек пользователя в **PostgreSQL**  
- 🔄 Смена стиля в любой момент командой `/style`  
- 🌐 Поддержка городов на английском языке (например, `Moscow`, `London`)  
- 🧠 Fallback‑советы, если AI недоступен  
- ❌ Команда `/cancel` для сброса диалога  

---

## 🏗 Архитектура проекта

Проект построен по модульному принципу с асинхронными клиентами и Orchestrator:

```
weatherAI/
├─ core/
│ ├─ init.py
│ └─ orchestrator.py # Orchestrator: связывает бота, AI и погоду
├─ clients/
│ ├─ init.py
│ ├─ ai_client.py # Mistral AI клиент
│ └─ weather_client.py # OpenWeatherMap клиент
├─ db/
│ ├─ init.py
│ └─ database.py # PostgreSQL база данных
├─ main.py # Telegram бот
└─ config.py # Конфигурации (API ключи, токены)
```


**Компоненты:**

- **API Client** — получение текущей погоды и прогноза на 5 дней (OpenWeatherMap)  
- **AI Client** — генерация рекомендаций через Mistral AI (`aiohttp`) с fallback‑советами  
- **DB** — асинхронная база PostgreSQL (`asyncpg`) с таблицами `users` и `history`  
- **UI** — Telegram‑бот с интерактивными кнопками и управлением состояниями  
- **Orchestrator** — управляет потоком данных и обработкой ошибок  

---

## 🛠 Технологии

- Python 3.14+  
- `python-telegram-bot` (v20+) — асинхронный фреймворк для бота  
- `aiohttp` — асинхронные HTTP-запросы к API  
- `asyncpg` — асинхронный драйвер PostgreSQL  
- PostgreSQL — основная база данных  
- OpenWeatherMap API — прогноз погоды  
- Mistral AI API — генерация текстов (`mistral-tiny` бесплатный тариф)  

---

## 📦 Установка и запуск

### 1. Клонируем репозиторий

```bash
git clone https://github.com/USERNAME/weatherAI.git
cd weatherAI
```

### 2. Устанавливаем зависимости
```
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```