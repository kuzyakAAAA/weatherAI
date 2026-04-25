import aiohttp
import json
import asyncio
from config import MISTRAL_API_KEY

class MistralAIClient:
    def __init__(self):
        self.api_key = MISTRAL_API_KEY
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-tiny"

    async def generate_advice(self, weather: dict, user_style: str = "casual", activity: str = "walk") -> str:
        # Безопасное извлечение данных с значениями по умолчанию
        temp = weather.get("temp", 0)
        feels_like = weather.get("feels_like", temp)
        condition = weather.get("condition", "ясно")
        wind_speed = weather.get("wind_speed", 0)

        prompt = f"""
Ты эксперт по одежде. Дай один короткий совет (2-3 предложения) без перечислений и маркированных списков.

Погода: {temp}°C, ощущается {feels_like}°C, {condition}, ветер {wind_speed} м/с.
Стиль: {user_style}, активность: {activity}.

Что надеть (головной убор, верх, обувь, аксессуары).
"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 400
        }

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        # Не используем logger, просто печатаем ошибку (или можно передать в fallback)
                        print(f"Mistral API error: {resp.status} - {await resp.text()}")
                        return self._fallback_advice(weather)
                    data = await resp.json()
                    advice = data["choices"][0]["message"]["content"].strip()
                    # Очистка от лишних переводов строк
                    advice = " ".join(advice.split())
                    return advice
            except asyncio.TimeoutError:
                print("Mistral API timeout")
                return self._fallback_advice(weather)
            except Exception as e:
                print(f"Exception calling Mistral: {e}")
                return self._fallback_advice(weather)

    def _fallback_advice(self, weather: dict) -> str:
        temp = weather.get("temp", 0)
        if temp < -10:
            return "Очень холодно! Наденьте тёплую куртку, шапку, шарф и варежки."
        elif temp < 0:
            return "Холодно. Пальто или пуховик, шапка, перчатки."
        elif temp < 10:
            return "Прохладно. Осенняя куртка, возможно шапка и зонт."
        elif temp < 20:
            return "Тепло. Лёгкая куртка или толстовка."
        else:
            return "Жарко. Футболка, шорты, головной убор."