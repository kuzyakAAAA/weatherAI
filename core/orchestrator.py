import logging
from clients.weather_client import WeatherClient
from clients.ai_client import MistralAIClient
from db.database import Database

STYLES = ("casual", "business", "sport")

class OutfitOrchestrator:
    def __init__(self, db: Database = None):
        self.db = db if db else Database()
        self.weather_client = WeatherClient()
        self.ai_client = MistralAIClient()

    async def _safe_generate_advice(self, weather: dict, style: str, activity: str) -> str:
        try:
            return await self.ai_client.generate_advice(weather, style, activity)
        except Exception as e:
            logging.error(f"AI Client error: {e}")
            return "💡 Совет недоступен, ориентируйтесь на погоду самостоятельно."

    async def get_recommendation(self, user_id: int, city: str, activity: str = "walk") -> str:
        user = await self.db.get_user(user_id)
        style = user["style"] if user else "casual"

        try:
            weather = await self.weather_client.get_weather(city)
        except Exception as e:
            logging.error(f"Weather API error for city '{city}': {e}")
            return f"❌ Не удалось получить погоду для города '{city}': {str(e)}"

        advice = await self._safe_generate_advice(weather, style, activity)

        try:
            await self.db.save_history(user_id, city, weather, advice)
            if not user:
                await self.db.save_user(user_id, style, city)
        except Exception as e:
            logging.error(f"DB error: {e}")

        return self._format_response(weather, advice)

    async def get_recommendation_for_date(self, user_id: int, city: str, target_date: str, activity: str = "walk") -> str:
        user = await self.db.get_user(user_id)
        style = user["style"] if user else "casual"

        try:
            weather = await self.weather_client.get_forecast_for_date(city, target_date)
        except Exception as e:
            logging.error(f"Weather API error for city '{city}' on {target_date}: {e}")
            return f"❌ Не удалось получить прогноз для города '{city}' на {target_date}: {str(e)}"

        advice = await self._safe_generate_advice(weather, style, activity)

        try:
            await self.db.save_history(user_id, city, weather, advice)
            if not user:
                await self.db.save_user(user_id, style, city)
        except Exception as e:
            logging.error(f"DB error: {e}")

        return self._format_response(weather, advice, target_date)

    def _format_response(self, weather: dict, advice: str, target_date: str = None) -> str:
        date_line = f"📅 Прогноз на {target_date}\n" if target_date else \
                    (f"📅 Прогноз на {weather.get('datetime')}\n" if weather.get('datetime') else "")
        return (
            f"{date_line}"
            f"📍 {weather.get('city')}, {weather.get('country')}\n"
            f"🌡 {weather.get('temp')}°C, ощущается как {weather.get('feels_like')}°C\n"
            f"☁️ {weather.get('condition').capitalize()}\n"
            f"💨 Ветер {weather.get('wind_speed')} м/с\n"
            f"💧 Влажность {weather.get('humidity')}%\n\n"
            f"🧥 Рекомендация:\n{advice}"
        )