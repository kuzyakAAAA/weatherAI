# работа с базой данных через SQLAlchemy ORM
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import DATABASE_URL


# базовый класс для ORM-моделей SQLAlchemy
class Base(DeclarativeBase):
    pass


# таблица users хранит пользователя, стиль одежды и предпочитаемый город
class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="casual", server_default="casual")
    preferred_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    history: Mapped[list["History"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# таблица history хранит историю запросов и советов
class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    weather_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    advice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="history")


# класс работы с базой данных PostgreSQL через SQLAlchemy
class Database:
    # инициализация объекта базы
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    # инициализация подключения к базе данных
    # название init_pool сохранено, чтобы не менять main.py
    async def init_pool(self):
        try:
            self.engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
            )

            self.session_factory = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
            )

            await self._init_tables()

        except Exception as e:
            logging.error(f"DB init error: {e}")
            raise

    # создание таблиц, если их нет
    async def _init_tables(self):
        if not self.engine:
            raise RuntimeError("Database engine is not initialized")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # получение новой асинхронной сессии SQLAlchemy
    def _session(self) -> AsyncSession:
        if not self.session_factory:
            raise RuntimeError("Database session factory is not initialized")
        return self.session_factory()

    # сериализация словаря погоды в JSON для хранения в базе данных
    def _serialize_weather(self, weather: dict) -> str:
        return json.dumps(weather, ensure_ascii=False)

    # получение пользователя по ID
    async def get_user(self, user_id: int):
        async with self._session() as session:
            user = await session.get(User, user_id)
            if not user:
                return None
            return {
                "style": user.style,
                "preferred_city": user.preferred_city,
            }

    # сохранение пользователя в базе
    async def save_user(self, user_id: int, style: str = "casual", preferred_city: str = None):
        async with self._session() as session:
            async with session.begin():
                user = await session.get(User, user_id)

                if user:
                    user.style = style
                    user.preferred_city = preferred_city
                else:
                    session.add(User(
                        user_id=user_id,
                        style=style,
                        preferred_city=preferred_city,
                    ))

    # сохранение истории запроса
    async def save_history(self, user_id: int, city: str, weather: dict, advice: str):
        weather_json = self._serialize_weather(weather)

        async with self._session() as session:
            async with session.begin():
                # на случай, если save_history вызвали до создания пользователя
                user = await session.get(User, user_id)
                if not user:
                    session.add(User(user_id=user_id))

                session.add(History(
                    user_id=user_id,
                    city=city,
                    weather_json=weather_json,
                    advice=advice,
                ))

    # закрытие соединений
    async def close(self):
        if self.engine:
            await self.engine.dispose()