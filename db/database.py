# работа с базой данных через SQLAlchemy ORM
import json # для преобразования словаря с погодой в JSON-строку
import logging # для логирования ошибок при подключении и работе с базой данных
from datetime import datetime # для сохранения даты и времени создания записей

from sqlalchemy import (
    BigInteger, # тип для больших чисел, используется для Telegram user_id
    Column, # используется для описания колонок таблицы
    DateTime, # тип данных для даты и времени
    ForeignKey, # используется для создания связи между таблицами
    Integer, # целочисленный тип данных
    String, # строковый тип данных с ограничением длины
    Text, # текстовый тип данных для длинных строк
)

from sqlalchemy.ext.asyncio import (
    async_sessionmaker, # фабрика для создания асинхронных сессий
    create_async_engine, # функция для создания асинхронного engine
)

from sqlalchemy.orm import (
    declarative_base, # создаёт базовый класс для ORM-моделей
    relationship, # описывает связи между таблицами
)

from config import DATABASE_URL # строка подключения к базе данных


# создаём базовый класс для всех ORM-моделей
# от него будут наследоваться классы таблиц
Base = declarative_base()


# модель пользователя
# этот класс соответствует таблице users в базе данных
class User(Base):
    __tablename__ = "users" # название таблицы в базе данных

    # Telegram ID пользователя
    # используется как первичный ключ, потому что он уникален для каждого пользователя
    user_id = Column(BigInteger, primary_key=True)

    # выбранный стиль одежды пользователя
    # по умолчанию используется casual
    style = Column(String(50), nullable=False, default="casual")

    # дата и время создания пользователя в базе данных
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # связь один-ко-многим:
    # один пользователь может иметь много записей в истории запросов
    history = relationship(
        "History",
        back_populates="user", # связывает с полем user в модели History
        cascade="all, delete-orphan", # при удалении пользователя удаляются все его записи в истории
    )


# модель истории запросов
# этот класс соответствует таблице history в базе данных
class History(Base):
    __tablename__ = "history" # название таблицы в базе данных

    # уникальный ID записи истории
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ID пользователя, которому принадлежит запись истории
    # ForeignKey связывает history.user_id с users.user_id
    user_id = Column(
        BigInteger,
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    # город, который ввёл пользователь
    city = Column(String(100), nullable=False)

    # данные о погоде в формате JSON-строки
    weather_json = Column(Text, nullable=False)

    # рекомендация по одежде, которую сгенерировал AI
    advice = Column(Text, nullable=False)

    # дата и время создания записи истории
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # обратная связь с пользователем
    # через неё можно получить пользователя, которому принадлежит запись истории
    user = relationship("User", back_populates="history")


# класс для работы с базой данных
# здесь находятся подключение, создание таблиц и методы для работы с данными
class Database:
    # инициализация объекта базы данных
    def __init__(self):
        self.engine = None # здесь будет храниться подключение к базе данных
        self.session_factory = None # фабрика для создания сессий

    # инициализация подключения к базе данных
    # название init_pool сохранено, чтобы не менять main.py
    async def init_pool(self):
        try:
            # создаём асинхронный engine для подключения к PostgreSQL
            self.engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                pool_pre_ping=True, # если соединение умерло, он попробует восстановить его
            )

            # создаём фабрику сессий
            # через неё дальше будут выполняться запросы к базе данных
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,  # SQLAlchemy после сохранения изменений считает данные объекта устаревшими и при следующем обращении к полю пытается заново загрузить их из базы.
            )

            # создаём таблицы, если они ещё не существуют
            await self._init_tables()

        except Exception as e:
            # если подключение или создание таблиц завершилось ошибкой,
            # записываем ошибку в лог и пробрасываем её дальше
            logging.error(f"DB init error: {e}")
            raise

    # создание таблиц в базе данных
    async def _init_tables(self):
        # проверяем, что engine уже создан
        if not self.engine:
            raise RuntimeError("Database engine is not initialized")

        # открываем подключение и создаём все таблицы,
        # которые описаны через ORM-модели User и History
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all) # это синхронная функция SQLAlchemy, а у тебя подключение асинхронное. Поэтому используется специальный мост: conn.sync - выполни синхронную функцию создания таблиц внутри асинхронного подключения.

    # создание новой асинхронной сессии
    def _session(self):
        # проверяем, что фабрика сессий уже создана
        if not self.session_factory:
            raise RuntimeError("Database session factory is not initialized")

        # возвращаем новую сессию для работы с базой данных
        return self.session_factory()

    # получение пользователя по его Telegram ID
    async def get_user(self, user_id: int):
        async with self._session() as session:
            # ищем пользователя по первичному ключу
            user = await session.get(User, user_id)

            # если пользователь не найден, возвращаем None
            if not user:
                return None

            # возвращаем данные пользователя в виде словаря
            return {
                "style": user.style,
            }

    # сохранение нового пользователя или обновление стиля существующего пользователя
    async def save_user(self, user_id: int, style: str = "casual"):
        async with self._session() as session:
            # открываем транзакцию
            async with session.begin():
                # проверяем, есть ли уже такой пользователь в базе
                user = await session.get(User, user_id)

                # если пользователь есть, обновляем его стиль
                if user:
                    user.style = style

                # если пользователя нет, создаём новую запись
                else:
                    session.add(
                        User(
                            user_id=user_id,
                            style=style,
                        )
                    )

    # сохранение истории запроса пользователя
    async def save_history(self, user_id: int, city: str, weather: dict, advice: str):
        # преобразуем словарь с погодой в JSON-строку,
        # чтобы сохранить его в текстовое поле базы данных
        weather_json = json.dumps(weather, ensure_ascii=False)

        async with self._session() as session:
            # открываем транзакцию
            async with session.begin():
                # проверяем, существует ли пользователь
                user = await session.get(User, user_id)

                # если история сохраняется раньше, чем пользователь был создан,
                # создаём пользователя со стилем по умолчанию
                if not user:
                    session.add(User(user_id=user_id))

                # добавляем новую запись в историю запросов
                session.add(
                    History(
                        user_id=user_id,
                        city=city,
                        weather_json=weather_json,
                        advice=advice,
                    )
                )

    # закрытие подключения к базе данных
    async def close(self):
        # если engine был создан, закрываем все соединения
        if self.engine:
            await self.engine.dispose()