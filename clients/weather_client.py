# импортируем aiohttp и datetime
import aiohttp
import logging
from datetime import datetime
from config import WEATHER_API_KEY

# клиент для получения текущей погоды и прогноза
class WeatherClient:
    # инициализация клиента с API ключом
    def __init__(self):
        self.current_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.api_key = WEATHER_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=10)

    # получение текущей погоды для города
    async def get_weather(self, city: str):
        # создание параметров запроса для получения погоды
        # отправка запроса к weather API
        params = {"q": city, "appid": self.api_key, "units": "metric", "lang": "ru"}
        try:
            # создается сессия для запроса к OpenWeather API
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # отправка запроса к API и обработка ответа
                async with session.get(self.current_url, params=params) as resp:
                    if resp.status != 200:
                        error_data = await resp.json()
                        raise Exception(f"{error_data.get('message', 'Unknown error')}")
                    data = await resp.json()
        except Exception as e:
            logging.error(f"WeatherClient get_weather error for '{city}': {e}")
            raise

        # возвращаем словарь с ключевыми данными
        return {
            "temp": data.get("main", {}).get("temp", 0),
            "feels_like": data.get("main", {}).get("feels_like", 0),
            "condition": data.get("weather", [{}])[0].get("description", "ясно"),
            "wind_speed": data.get("wind", {}).get("speed", 0),
            "humidity": data.get("main", {}).get("humidity", 0),
            "city": data.get("name", city),
            "country": data.get("sys", {}).get("country", ""),
        }

    # получение прогноза на конкретную дату
    async def get_forecast_for_date(self, city: str, target_date: str):
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise Exception("Неверный формат даты. Используйте ГГГГ-ММ-ДД")

        today = datetime.now().date()
        if target < today:
            raise Exception("Дата не может быть в прошлом")
        if (target - today).days > 5:
            raise Exception("Прогноз доступен только на ближайшие 5 дней")

        # отправка запроса к forecast API
        params = {"q": city, "appid": self.api_key, "units": "metric", "lang": "ru"}
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.forecast_url, params=params) as resp:
                    if resp.status != 200:
                        error_data = await resp.json()
                        raise Exception(f"{error_data.get('message', 'Unknown error')}")
                    data = await resp.json()
        except Exception as e:
            logging.error(f"WeatherClient get_forecast_for_date error for '{city}' on {target_date}: {e}")
            raise

        # выбираем прогноз, ближайший к полудню на целевую дату
        # в API OpenWeather прогнозы идут с шагом 3 часа, поэтому ищем запись с временем, наиболее близким к 12:00
        best_entry = None
        best_diff = 24
        for entry in data.get("list", []):
            dt = datetime.fromtimestamp(entry.get("dt", 0))
            if dt.date() == target:
                diff = abs(dt.hour - 12)
                if diff < best_diff:
                    best_diff = diff
                    best_entry = entry

        if not best_entry:
            raise Exception(f"Нет данных для {target_date}. Прогноз доступен на 5 дней вперёд.")

        # возвращаем словарь с прогнозом
        return {
            "temp": best_entry.get("main", {}).get("temp", 0),
            "feels_like": best_entry.get("main", {}).get("feels_like", 0),
            "condition": best_entry.get("weather", [{}])[0].get("description", "ясно"),
            "wind_speed": best_entry.get("wind", {}).get("speed", 0),
            "humidity": best_entry.get("main", {}).get("humidity", 0),
            "city": data.get("city", {}).get("name", city),
            "country": data.get("city", {}).get("country", ""),
            "datetime": datetime.fromtimestamp(best_entry.get("dt", 0)).strftime("%Y-%m-%d %H:%M")
        }