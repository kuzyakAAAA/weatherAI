import aiohttp
from datetime import datetime, timedelta
from config import WEATHER_API_KEY

class WeatherClient:
    def __init__(self):
        self.current_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.api_key = WEATHER_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def get_weather(self, city: str):
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "ru"
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(self.current_url, params=params) as resp:
                if resp.status != 200:
                    error_data = await resp.json()
                    raise Exception(f"Ошибка погоды: {error_data.get('message', 'Неизвестная ошибка')}")
                data = await resp.json()
                weather = {
                    "temp": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "condition": data["weather"][0]["description"],
                    "wind_speed": data["wind"]["speed"],
                    "humidity": data["main"]["humidity"],
                    "city": data["name"],
                    "country": data["sys"]["country"]
                }
                return weather

    async def get_forecast_for_date(self, city: str, target_date: str):
        """
        target_date: строка в формате 'YYYY-MM-DD'
        Возвращает погоду на ближайший к 12:00 срез в указанную дату.
        Доступно на 5 дней вперёд от текущей даты.
        """
        # Проверка корректности даты
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise Exception("Неверный формат даты. Используйте ГГГГ-ММ-ДД")
        today = datetime.now().date()
        if target < today:
            raise Exception("Дата не может быть в прошлом")
        if (target - today).days > 5:
            raise Exception("Прогноз доступен только на 5 дней вперёд")

        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "ru"
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(self.forecast_url, params=params) as resp:
                if resp.status != 200:
                    error_data = await resp.json()
                    raise Exception(f"Ошибка прогноза: {error_data.get('message', 'Неизвестная ошибка')}")
                data = await resp.json()

                best_entry = None
                best_diff = 24  # разница в часах
                for entry in data["list"]:
                    dt = datetime.fromtimestamp(entry["dt"])
                    if dt.date() == target:
                        diff = abs(dt.hour - 12)
                        if diff < best_diff:
                            best_diff = diff
                            best_entry = entry
                if not best_entry:
                    raise Exception(f"Нет данных для {target_date}. Прогноз доступен на 5 дней вперёд.")

                weather = {
                    "temp": best_entry["main"]["temp"],
                    "feels_like": best_entry["main"]["feels_like"],
                    "condition": best_entry["weather"][0]["description"],
                    "wind_speed": best_entry["wind"]["speed"],
                    "humidity": best_entry["main"]["humidity"],
                    "city": data["city"]["name"],
                    "country": data["city"]["country"],
                    "datetime": datetime.fromtimestamp(best_entry["dt"]).strftime("%Y-%m-%d %H:%M")
                }
                return weather