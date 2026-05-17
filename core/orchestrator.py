# импортируем клиенты, базу данных и логирование
import logging # для логирования ошибок при работе с погодой, AI и базой данных

from clients.weather_client import WeatherClient # клиент для получения погоды через API
from clients.ai_client import MistralAIClient # клиент для генерации рекомендаций через Mistral AI
from db.database import Database # класс для работы с базой данных


# класс orchestrator управляет основной логикой приложения
# он связывает Telegram-бота, погоду, AI и базу данных
class OutfitOrchestrator:
    # инициализация orchestrator с клиентами и базой данных
    def __init__(self, db: Database = None):
        # если база данных передана из main.py, используем её
        # если не передана, создаём новый объект Database
        self.db = db if db else Database()

        # создаём клиент для получения текущей погоды и прогноза
        self.weather_client = WeatherClient()

        # создаём клиент для генерации советов по одежде через AI
        self.ai_client = MistralAIClient()

    # получение стиля пользователя из базы данных
    async def _get_user_style(self, user_id: int) -> str:
        try:
            # пытаемся найти пользователя в базе данных
            user = await self.db.get_user(user_id)

            # если пользователь найден, берём его сохранённый стиль
            if user:
                return user["style"]

        except Exception as e:
            # если при получении пользователя возникла ошибка,
            # записываем её в лог и используем стиль по умолчанию
            logging.error(f"DB error while getting user style: {e}")

        # если пользователь не найден или произошла ошибка,
        # используем стиль по умолчанию
        return "casual"

    # безопасная генерация совета через AI
    # если AI недоступен, бот не падает, а возвращает fallback-совет
    async def _safe_generate_advice(self, weather: dict, style: str, activity: str) -> str:
        try:
            # отправляем данные о погоде, стиле и активности в AI-клиент
            return await self.ai_client.generate_advice(weather, style, activity)

        except Exception as e:
            # если AI-клиент вернул ошибку, записываем её в лог
            logging.error(f"AI Client error: {e}")

            # возвращаем простой запасной совет
            return "💡 Совет недоступен, ориентируйтесь на погоду самостоятельно."

    # безопасное сохранение истории запроса в базу данных
    async def _safe_save_history(self, user_id: int, city: str, weather: dict, advice: str):
        try:
            # сохраняем город, погоду и рекомендацию в таблицу history
            await self.db.save_history(user_id, city, weather, advice)

        except Exception as e:
            # если история не сохранилась, бот всё равно продолжит работу
            logging.error(f"DB error while saving history: {e}")

    # общий метод для получения рекомендации
    # используется и для сегодняшней погоды, и для прогноза на конкретную дату
    async def _build_recommendation(
        self,
        user_id: int,
        city: str,
        weather: dict,
        activity: str = "walk",
        target_date: str = None,
    ) -> str:
        # получаем стиль пользователя из базы данных
        style = await self._get_user_style(user_id)

        # генерируем совет по одежде через AI
        advice = await self._safe_generate_advice(weather, style, activity)

        # сохраняем историю запроса в базу данных
        await self._safe_save_history(user_id, city, weather, advice)

        # форматируем и возвращаем готовый ответ пользователю
        return self._format_response(weather, advice, target_date)

    # получение рекомендации на сегодня
    async def get_recommendation(self, user_id: int, city: str, activity: str = "walk") -> str:
        # получаем текущую погоду для выбранного города
        try:
            weather = await self.weather_client.get_weather(city)

        except Exception as e:
            # если погоду получить не удалось, записываем ошибку в лог
            logging.error(f"Weather API error for city '{city}': {e}")

            # возвращаем пользователю понятное сообщение об ошибке
            return f"❌ Не удалось получить погоду для города '{city}': {str(e)}"

        # собираем итоговую рекомендацию
        return await self._build_recommendation(
            user_id=user_id,
            city=city,
            weather=weather,
            activity=activity,
        )

    # получение рекомендации на конкретную дату
    async def get_recommendation_for_date(
        self,
        user_id: int,
        city: str,
        target_date: str,
        activity: str = "walk",
    ) -> str:
        # получаем прогноз погоды на выбранную дату
        try:
            weather = await self.weather_client.get_forecast_for_date(city, target_date)

        except Exception as e:
            # если прогноз получить не удалось, записываем ошибку в лог
            logging.error(f"Weather API error for city '{city}' on {target_date}: {e}")

            # возвращаем пользователю понятное сообщение об ошибке
            return f"❌ Не удалось получить прогноз для города '{city}' на {target_date}: {str(e)}"

        # собираем итоговую рекомендацию
        return await self._build_recommendation(
            user_id=user_id,
            city=city,
            weather=weather,
            activity=activity,
            target_date=target_date,
        )

    # форматирование текста ответа пользователю
    def _format_response(self, weather: dict, advice: str, target_date: str = None) -> str:
        # если передана конкретная дата, показываем её
        if target_date:
            date_line = f"📅 Прогноз на {target_date}\n"

        # если конкретной даты нет, но дата есть в погодных данных, показываем её
        elif weather.get("datetime"):
            date_line = f"📅 Прогноз на {weather.get('datetime')}\n"

        # если даты нет, строку с датой не выводим
        else:
            date_line = ""

        # получаем описание погоды
        condition = weather.get("condition", "нет данных")

        # если описание погоды является строкой, делаем первую букву заглавной
        if isinstance(condition, str):
            condition = condition.capitalize()

        # собираем красивый текст ответа для Telegram
        return (
            f"{date_line}"
            f"📍 {weather.get('city')}, {weather.get('country')}\n"
            f"🌡 {weather.get('temp')}°C, ощущается как {weather.get('feels_like')}°C\n"
            f"☁️ {condition}\n"
            f"💨 Ветер {weather.get('wind_speed')} м/с\n"
            f"💧 Влажность {weather.get('humidity')}%\n\n"
            f"🧥 Рекомендация:\n{advice}"
        )