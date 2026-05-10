# импортируем aiohttp и asyncio для асинхронных запросов
import aiohttp
import asyncio
import logging
from config import MISTRAL_API_KEY

# клиент для генерации рекомендаций через Mistral AI
class MistralAIClient:
    # инициализация клиента с API ключом
    def __init__(self):
        self.api_key = MISTRAL_API_KEY
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-tiny"

    # генерация совета на основе погоды, стиля и активности
    async def generate_advice(self, weather: dict, user_style: str = "casual", activity: str = "walk") -> str:
        temp = weather.get("temp", 0)
        feels_like = weather.get("feels_like", temp)
        condition = weather.get("condition", "ясно")
        wind_speed = weather.get("wind_speed", 0)

        # формируем prompt для AI
        prompt = f"""
Ты эксперт по одежде. Дай один короткий совет (2-3 предложения) без списков.

Погода: {temp}°C, ощущается {feels_like}°C, {condition}, ветер {wind_speed} м/с.
Стиль: {user_style}, активность: {activity}.
Что надеть (головной убор, верх, обувь, аксессуары).
"""
        headers = {"Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"}
        payload = {"model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 400}

        # делаем асинхронный POST запрос к API и задаем таймаут
        timeout = aiohttp.ClientTimeout(total=15)
        
        # обрабатываем ответ и возвращаем совет, или фоллбек при ошибке
        try:
            # создается сессия для запроса к Mistral API
            # async with гарантирует закрытие сессии после выполнения блока
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        logging.error(f"Mistral API error {resp.status}: {await resp.text()}")
                        # resp.text() читает текстовое содержимое HTTP-ответа сервера для логирования ошибки, а resp.json() читает и парсит JSON-ответ для получения данных. В случае ошибки мы логируем текст ответа, который может содержать сообщение об ошибке от сервера, а не пытаемся парсить JSON, который может быть некорректным при ошибке.
                        return self._fallback_advice(weather)
                    data = await resp.json()
                    advice = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    advice = " ".join(advice.split())
                    return advice if advice else self._fallback_advice(weather)
        except asyncio.TimeoutError:
            logging.error("Mistral API timeout")
            return self._fallback_advice(weather)
        except Exception as e:
            logging.error(f"Exception calling Mistral: {e}")
            return self._fallback_advice(weather)

    # fallback совет если AI недоступен
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