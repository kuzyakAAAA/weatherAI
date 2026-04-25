from clients.weather_client import WeatherClient
from clients.ai_client import MistralAIClient
from db.database import Database

class OutfitOrchestrator:
    def __init__(self, db=None):
        self.db = db if db else Database()
        self.weather_client = WeatherClient()
        self.ai_client = MistralAIClient()

    async def get_recommendation(self, user_id: int, city: str, activity: str = "walk"):
        # 1. Получаем стиль пользователя из БД (по умолчанию "casual")
        user = await self.db.get_user(user_id)          # добавлен await
        style = user["style"] if user else "casual"

        # 2. Получаем текущую погоду
        try:
            weather = await self.weather_client.get_weather(city)
        except Exception as e:
            return f"❌ Не удалось получить погоду для города '{city}': {str(e)}"

        # 3. Генерируем совет через AI
        advice = await self.ai_client.generate_advice(weather, style, activity)

        # 4. Сохраняем в историю
        await self.db.save_history(user_id, city, weather, advice)

        # 5. Если у пользователя ещё нет предпочтений, сохраняем город (опционально)
        if not user:
            await self.db.save_user(user_id, style, city)

        # 6. Форматируем ответ
        return self._format_response(weather, advice)

    async def get_recommendation_for_date(self, user_id: int, city: str, target_date: str, activity: str = "walk"):
        """Получить рекомендацию на конкретную дату (прогноз)"""
        # 1. Получаем стиль пользователя
        user = await self.db.get_user(user_id)          # добавлен await
        style = user["style"] if user else "casual"

        # 2. Получаем прогноз погоды на указанную дату
        try:
            weather = await self.weather_client.get_forecast_for_date(city, target_date)
        except Exception as e:
            return f"❌ Не удалось получить прогноз для города '{city}' на {target_date}: {str(e)}"

        # 3. Генерируем совет через AI
        advice = await self.ai_client.generate_advice(weather, style, activity)

        # 4. Сохраняем в историю
        await self.db.save_history(user_id, city, weather, advice)

        # 5. Если пользователь новый – сохраняем стиль и город
        if not user:
            await self.db.save_user(user_id, style, city)

        # 6. Форматируем ответ с датой
        return self._format_response(weather, advice, target_date)

    def _format_response(self, weather, advice, target_date=None):
        date_line = ""
        if target_date:
            date_line = f"📅 Прогноз на {target_date}\n"
        elif weather.get("datetime"):
            date_line = f"📅 Прогноз на {weather['datetime']}\n"

        return (
            f"{date_line}"
            f"📍 {weather['city']}, {weather['country']}\n"
            f"🌡 {weather['temp']}°C, ощущается как {weather['feels_like']}°C\n"
            f"☁️ {weather['condition']}\n"
            f"💨 Ветер {weather['wind_speed']} м/с\n"
            f"💧 Влажность {weather['humidity']}%\n\n"
            f"🧥 Рекомендация:\n{advice}"
        )