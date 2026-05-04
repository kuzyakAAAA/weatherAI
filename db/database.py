# импортируем asyncpg и json
import asyncpg
import json
import logging
from config import DATABASE_URL

# класс работы с базой данных PostgreSQL
class Database:
    # инициализация объекта базы
    def __init__(self):
        self.pool = None

    # инициализация пула соединений
    async def init_pool(self):
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            await self._init_tables()
        except Exception as e:
            logging.error(f"DB pool init error: {e}")
            raise

    # создание таблиц, если их нет
    async def _init_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    style TEXT DEFAULT 'casual',
                    preferred_city TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    city TEXT,
                    weather_json TEXT,
                    advice TEXT,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

    # сериализация погоды в JSON
    def _serialize_weather(self, weather: dict) -> str:
        return json.dumps(weather, ensure_ascii=False)

    # получение пользователя по ID
    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT style, preferred_city FROM users WHERE user_id = $1", user_id)
            return {"style": row["style"], "preferred_city": row["preferred_city"]} if row else None

    # сохранение пользователя в базе
    async def save_user(self, user_id: int, style: str = "casual", preferred_city: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, style, preferred_city)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET style=$2, preferred_city=$3
            """, user_id, style, preferred_city)

    # сохранение истории запроса
    async def save_history(self, user_id: int, city: str, weather: dict, advice: str):
        weather_json = self._serialize_weather(weather)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO history (user_id, city, weather_json, advice)
                VALUES ($1, $2, $3, $4)
            """, user_id, city, weather_json, advice)

    # закрытие пула соединений
    async def close(self):
        if self.pool:
            await self.pool.close()