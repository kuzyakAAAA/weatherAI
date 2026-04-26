# подключаем клиентов погоды, ии и базу данных
from clients.weather_client import WeatherClient
from clients.ai_client import MistralAIClient
from db.database import Database

class OutfitOrchestrator:
    def __init__(self, db=None):
        # сохраняем бд (или создаём новую) и инициализируем клиентов
        self.db = db if db else Database()
        self.weather_client = WeatherClient()
        self.ai_client = MistralAIClient()

    async def get_recommendation(self, user_id: int, city: str, activity: str = "walk"):
        # получаем стиль пользователя из бд, по умолчанию casual
        user = await self.db.get_user(user_id)
        style = user["style"] if user else "casual"

        # запрашиваем текущую погоду через api
        try:
            weather = await self.weather_client.get_weather(city)
        except Exception as e:
            return f"❌ Не удалось получить погоду для города '{city}': {str(e)}"

        # генерируем текстовый совет через ии
        advice = await self.ai_client.generate_advice(weather, style, activity)

        # сохраняем запрос и ответ в историю
        await self.db.save_history(user_id, city, weather, advice)

        # если пользователь новый, добавляем его в таблицу users
        if not user:
            await self.db.save_user(user_id, style, city)

        # возвращаем красиво отформатированный ответ
        return self._format_response(weather, advice)

    async def get_recommendation_for_date(self, user_id: int, city: str, target_date: str, activity: str = "walk"):
        # получаем стиль пользователя (fallback casual)
        user = await self.db.get_user(user_id)
        style = user["style"] if user else "casual"

        # получаем прогноз погоды на указанную дату
        try:
            weather = await self.weather_client.get_forecast_for_date(city, target_date)
        except Exception as e:
            return f"❌ Не удалось получить прогноз для города '{city}' на {target_date}: {str(e)}"

        # генерируем совет через ии с учётом прогноза
        advice = await self.ai_client.generate_advice(weather, style, activity)

        # сохраняем историю запроса
        await self.db.save_history(user_id, city, weather, advice)

        # регистрируем нового пользователя, если его ещё нет
        if not user:
            await self.db.save_user(user_id, style, city)

        # возвращаем ответ с пометкой о дате прогноза
        return self._format_response(weather, advice, target_date)

    def _format_response(self, weather, advice, target_date=None):
        # добавляем строку с датой, если передан target_date или в данных есть datetime
        date_line = ""
        if target_date:
            date_line = f"📅 Прогноз на {target_date}\n"
        elif weather.get("datetime"):
            date_line = f"📅 Прогноз на {weather['datetime']}\n"

        # собираем итоговое сообщение: погода + рекомендация
        return (
            f"{date_line}"
            f"📍 {weather['city']}, {weather['country']}\n"
            f"🌡 {weather['temp']}°C, ощущается как {weather['feels_like']}°C\n"
            f"☁️ {weather['condition'].capitalize()}\n"
            f"💨 Ветер {weather['wind_speed']} м/с\n"
            f"💧 Влажность {weather['humidity']}%\n\n"
            f"🧥 Рекомендация:\n{advice}"
        )
