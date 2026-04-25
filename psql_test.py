import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect(
        user='postgres',
        password='root',
        host='localhost',
        port=5432,
        database='weather_db'
    )
    print("Подключено!")
    await conn.close()

asyncio.run(test())